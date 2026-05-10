"""FastAPI application exposing the soccer pick pipeline over HTTP.

The handler builds the same ``deps`` bundle the CLI uses (via
``dependency_bundle.build_dependency_bundle``) and delegates to
``pipeline_service.run_pipeline_with_payload`` so the response includes the
markdown report alongside the structured scoring/trace payload.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Make the soccer-prop-picks scripts importable without packaging.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from dependency_bundle import build_dependency_bundle  # noqa: E402
from pipeline_service import (  # noqa: E402
    PipelineServiceError,
    run_pipeline_with_payload,
)


class PicksRequest(BaseModel):
    """Request body for ``POST /picks``.

    Mirrors the CLI surface of ``run_match_pick_pipeline.py`` so the API and
    CLI stay in lockstep.
    """

    match_query: str = Field(..., description="e.g. 'arsenal - liverpool 2026-05-03'")
    top_n: int = Field(5, ge=1, le=5)
    competition: str = Field("League", description="Display label for the competition.")
    league: str | None = None
    league_id: str | None = None
    season: str | None = None
    use_llm: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    fixture_provider: str | None = Field(
        None, description="api-football | llm | auto. Defaults to env SOCCER_FIXTURE_PROVIDER."
    )
    fixture_llm_provider: str | None = None
    fixture_llm_model: str | None = None
    fixture_llm_base_url: str | None = None
    allow_deterministic_fallback: bool = False


class PicksResponse(BaseModel):
    report_markdown: str
    scores: list[dict[str, Any]]
    trace: dict[str, Any] | None = None
    match_inputs: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    providers: dict[str, bool]


def _provider_status() -> dict[str, bool]:
    """Report which credentials are configured without leaking values."""
    return {
        "api_football": bool(os.getenv("API_FOOTBALL_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "xai": bool(os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")),
        "fixture_llm": bool(os.getenv("SOCCER_FIXTURE_LLM_API_KEY")),
    }


def create_app() -> FastAPI:
    app = FastAPI(
        title="Colmillo-Picks API",
        version="0.1.0",
        description="HTTP wrapper around the soccer prop pick pipeline.",
    )

    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok", providers=_provider_status())

    @app.post("/picks", response_model=PicksResponse)
    def picks(payload: PicksRequest) -> PicksResponse:
        if payload.use_llm and not payload.llm_provider:
            raise HTTPException(
                status_code=400,
                detail="llm_provider is required when use_llm is true.",
            )

        try:
            deps = build_dependency_bundle(
                use_llm=payload.use_llm,
                llm_provider=payload.llm_provider,
                llm_model=payload.llm_model,
                allow_deterministic_fallback=payload.allow_deterministic_fallback,
                league=payload.league,
                league_id=payload.league_id,
                season=payload.season,
                fixture_provider_name=payload.fixture_provider,
                fixture_llm_provider=payload.fixture_llm_provider,
                fixture_llm_model=payload.fixture_llm_model,
                fixture_llm_base_url=payload.fixture_llm_base_url,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        request_dict = {
            "match_query": payload.match_query,
            "top_n": payload.top_n,
            "use_llm": payload.use_llm,
            "llm_provider": payload.llm_provider,
            "llm_model": payload.llm_model,
            "competition": payload.league or payload.competition,
        }

        try:
            result = run_pipeline_with_payload(request=request_dict, deps=deps)
        except PipelineServiceError as exc:
            cause = exc.__cause__
            message = str(cause) if cause else str(exc)
            status_code = 400 if exc.stage in {"parse", "collect"} else 502
            raise HTTPException(
                status_code=status_code,
                detail={"stage": exc.stage, "message": message},
            ) from exc

        return PicksResponse(**result)

    return app


app = create_app()
