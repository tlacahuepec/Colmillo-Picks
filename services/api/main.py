"""FastAPI application exposing the soccer pick pipeline over HTTP.

The handler builds the same ``deps`` bundle the CLI uses (via
``dependency_bundle.build_dependency_bundle``) and delegates to
``pipeline_service.run_pipeline_with_payload`` so the response includes the
markdown report alongside the structured scoring/trace payload.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
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
from services.api import db as db_module  # noqa: E402
from services.api.logging_config import configure_json_logging  # noqa: E402
from services.api.middleware import (  # noqa: E402
    APIKeyAuthMiddleware,
    RequestLoggingMiddleware,
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
    id: str
    created_at: datetime
    report_markdown: str
    scores: list[dict[str, Any]]
    trace: dict[str, Any] | None = None
    match_inputs: dict[str, Any]


class PickSummary(BaseModel):
    """Lightweight row used by ``GET /picks`` listings."""

    id: str
    created_at: datetime
    match_query: str
    competition: str | None = None
    top_n: int
    fixture_status: str | None = None
    llm_status: str | None = None
    latency_ms: int | None = None


class PicksListResponse(BaseModel):
    items: list[PickSummary]
    limit: int
    offset: int


class PickDetailResponse(BaseModel):
    id: str
    created_at: datetime
    match_query: str
    competition: str | None = None
    top_n: int
    fixture_status: str | None = None
    llm_status: str | None = None
    latency_ms: int | None = None
    request: dict[str, Any]
    report_markdown: str
    scores: list[dict[str, Any]]
    trace: dict[str, Any] | None = None


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


def _cors_origins() -> list[str]:
    """Parse ``COLMILLO_UI_ORIGIN`` into a list of allowed origins.

    Supports a single origin or a comma-separated list. Returns an empty list
    when unset, which disables cross-origin access (same-origin only).
    """
    raw = os.getenv("COLMILLO_UI_ORIGIN", "").strip()
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Colmillo-Picks API",
        version="0.1.0",
        description="HTTP wrapper around the soccer prop pick pipeline.",
    )

    # Outermost middleware runs last on the way in / first on the way out, so
    # add request logging first to ensure it sees the final status code.
    logger = configure_json_logging()
    app.add_middleware(APIKeyAuthMiddleware)
    app.add_middleware(RequestLoggingMiddleware, logger=logger)

    cors_origins = _cors_origins()
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-API-Key", "X-Request-Id"],
            allow_credentials=False,
        )

    db_module.init_db()

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
            started = time.perf_counter()
            result = run_pipeline_with_payload(request=request_dict, deps=deps)
            latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        except PipelineServiceError as exc:
            cause = exc.__cause__
            message = str(cause) if cause else str(exc)
            status_code = 400 if exc.stage in {"parse", "collect"} else 502
            raise HTTPException(
                status_code=status_code,
                detail={"stage": exc.stage, "message": message},
            ) from exc

        row = db_module.record_pick_run(
            request_payload=request_dict,
            result=result,
            latency_ms=latency_ms,
        )

        return PicksResponse(
            id=row.id,
            created_at=row.created_at,
            **result,
        )

    @app.get("/picks", response_model=PicksListResponse)
    def list_picks(
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> PicksListResponse:
        rows = db_module.list_pick_runs(limit=limit, offset=offset)
        items = [
            PickSummary(
                id=row.id,
                created_at=row.created_at,
                match_query=row.match_query,
                competition=row.competition,
                top_n=row.top_n,
                fixture_status=row.fixture_status,
                llm_status=row.llm_status,
                latency_ms=row.latency_ms,
            )
            for row in rows
        ]
        return PicksListResponse(items=items, limit=limit, offset=offset)

    @app.get("/picks/{pick_id}", response_model=PickDetailResponse)
    def get_pick(pick_id: str) -> PickDetailResponse:
        row = db_module.get_pick_run(pick_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Pick not found.")
        return PickDetailResponse(
            id=row.id,
            created_at=row.created_at,
            match_query=row.match_query,
            competition=row.competition,
            top_n=row.top_n,
            fixture_status=row.fixture_status,
            llm_status=row.llm_status,
            latency_ms=row.latency_ms,
            request=json.loads(row.request_json),
            report_markdown=row.report_markdown,
            scores=json.loads(row.scores_json),
            trace=json.loads(row.trace_json) if row.trace_json else None,
        )

    return app


app = create_app()
