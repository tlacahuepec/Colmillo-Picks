"""FastAPI application exposing the soccer pick pipeline over HTTP.

``POST /picks`` is async: it validates the request synchronously, persists a
``pending`` row, schedules a background task that runs the full pipeline, and
returns ``202`` immediately. Clients then poll ``GET /picks/{id}/status`` (or
``GET /picks/{id}`` for the full payload) to discover ``success`` / ``failed``.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

# Make the repo root and soccer-prop-picks scripts importable without packaging.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_SCRIPTS_DIR = _REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_REPO_ROOT / ".env")

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from dependency_bundle import build_dependency_bundle  # noqa: E402
from pipeline_service import (  # noqa: E402
    PipelineServiceError,
    run_pipeline_with_payload,
)
from services.api import db as db_module  # noqa: E402
from services.api import jobs as jobs_module  # noqa: E402
from services.api.logging_config import configure_json_logging  # noqa: E402
from services.api.middleware import (  # noqa: E402
    APIKeyAuthMiddleware,
    RequestLoggingMiddleware,
)
from services.api.sentry import init_sentry_if_configured  # noqa: E402


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #


class PicksRequest(BaseModel):
    """Request body for ``POST /picks``."""

    match_query: str = Field(..., description="e.g. 'arsenal - liverpool 2026-05-03'")
    top_n: int = Field(5, ge=1, le=5)
    competition: str = Field("League", description="Display label for the competition.")
    league: str | None = None
    use_llm: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    fixture_provider: str | None = Field(
        None, description="llm | auto. Defaults to env SOCCER_FIXTURE_PROVIDER."
    )
    fixture_llm_provider: str | None = None
    fixture_llm_model: str | None = None
    fixture_llm_base_url: str | None = None
    allow_deterministic_fallback: bool = False
    availability_provider: str | None = Field(
        None, description="prizepicks | mock | none. Defaults to env COLMILLO_AVAILABILITY_PROVIDER."
    )


class PickAcceptedResponse(BaseModel):
    """Body of the ``202`` returned by ``POST /picks``."""

    id: str
    status: str
    created_at: datetime


class PickStatusResponse(BaseModel):
    id: str
    status: str
    error_stage: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None


class PickSummary(BaseModel):
    """Lightweight row used by ``GET /picks`` listings."""

    id: str
    created_at: datetime
    match_query: str
    competition: str | None = None
    top_n: int
    status: str
    fixture_status: str | None = None
    llm_status: str | None = None
    latency_ms: int | None = None
    error_stage: str | None = None


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
    status: str
    fixture_status: str | None = None
    llm_status: str | None = None
    latency_ms: int | None = None
    error_stage: str | None = None
    error_message: str | None = None
    request: dict[str, Any]
    report_markdown: str
    scores: list[dict[str, Any]]
    trace: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    providers: dict[str, bool]


class OutcomeEntry(BaseModel):
    rank: int = Field(..., ge=1)
    player: str = Field(..., min_length=1, max_length=255)
    market: str = Field(..., min_length=1, max_length=64)
    result: Literal["win", "loss", "push", "void"]


class OutcomesRequest(BaseModel):
    outcomes: list[OutcomeEntry] = Field(..., min_length=1)


class OutcomeResponse(BaseModel):
    id: str
    pick_id: str
    rank: int
    player: str
    market: str
    result: str
    recorded_at: datetime


class OutcomesResponse(BaseModel):
    pick_id: str
    items: list[OutcomeResponse]


class HitRateResponse(BaseModel):
    totals: dict[str, int]
    decided: int
    hit_rate: float | None
    since: str | None = None


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _provider_status() -> dict[str, bool]:
    """Report which credentials are configured without leaking values."""
    return {
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "xai": bool(os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")),
        "fixture_llm": bool(os.getenv("SOCCER_FIXTURE_LLM_API_KEY")),
    }


def _cors_origins() -> list[str]:
    raw = os.getenv("COLMILLO_UI_ORIGIN", "").strip()
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _build_request_dict(payload: PicksRequest) -> dict[str, Any]:
    return {
        "match_query": payload.match_query,
        "top_n": payload.top_n,
        "use_llm": payload.use_llm,
        "llm_provider": payload.llm_provider,
        "llm_model": payload.llm_model,
        "competition": payload.league or payload.competition,
    }


def _row_to_summary(row: db_module.PickRun) -> PickSummary:
    return PickSummary(
        id=row.id,
        created_at=row.created_at,
        match_query=row.match_query,
        competition=row.competition,
        top_n=row.top_n,
        status=row.status,
        fixture_status=row.fixture_status,
        llm_status=row.llm_status,
        latency_ms=row.latency_ms,
        error_stage=row.error_stage,
    )


def _row_to_detail(row: db_module.PickRun) -> PickDetailResponse:
    return PickDetailResponse(
        id=row.id,
        created_at=row.created_at,
        match_query=row.match_query,
        competition=row.competition,
        top_n=row.top_n,
        status=row.status,
        fixture_status=row.fixture_status,
        llm_status=row.llm_status,
        latency_ms=row.latency_ms,
        error_stage=row.error_stage,
        error_message=row.error_message,
        request=json.loads(row.request_json) if row.request_json else {},
        report_markdown=row.report_markdown or "",
        scores=json.loads(row.scores_json) if row.scores_json else [],
        trace=json.loads(row.trace_json) if row.trace_json else None,
    )


def _build_run_ledger():
    from run_ledger import InMemoryRunLedger, SqliteRunLedger
    try:
        return SqliteRunLedger()
    except Exception:
        return InMemoryRunLedger()


def _execute_pipeline_job(
    *,
    pick_id: str,
    request_dict: dict[str, Any],
    bundle_kwargs: dict[str, Any],
) -> bool:
    """Background task body: run the pipeline and update the pending row."""
    ledger = _build_run_ledger()
    run_ctx = ledger.start_run(source="api", request=request_dict)

    started = time.perf_counter()
    try:
        deps = build_dependency_bundle(**bundle_kwargs)
        result = run_pipeline_with_payload(request=request_dict, deps=deps)
    except PipelineServiceError as exc:
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        cause = exc.__cause__
        message = str(cause) if cause else str(exc)
        db_module.mark_pick_failed(
            pick_id=pick_id, stage=exc.stage, message=message, latency_ms=latency_ms
        )
        ledger.fail_run(run_ctx.id, error_summary=message, error_stage=exc.stage)
        return False
    except Exception as exc:  # configuration / unexpected errors
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        db_module.mark_pick_failed(
            pick_id=pick_id, stage="unknown", message=str(exc), latency_ms=latency_ms
        )
        ledger.fail_run(run_ctx.id, error_summary=str(exc), error_stage="unknown")
        return False
    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    db_module.mark_pick_success(pick_id=pick_id, result=result, latency_ms=latency_ms)
    for step in result.get("steps", []):
        ledger.record_step(run_ctx.id, step["name"], status=step["status"], duration_ms=step["duration_ms"])
    ledger.save_picks(run_ctx.id, result.get("scores", []))
    failed_steps = [s for s in result.get("steps", []) if s["status"] == "failed"]
    if failed_steps:
        reasons = [f"{s['name']} failed" for s in failed_steps]
        ledger.partial_run(run_ctx.id, reasons=reasons)
    else:
        ledger.complete_run(run_ctx.id)
    return True


def _run_next_queued_job(
    pick_id: str,
    request_dict: dict[str, Any],
    bundle_kwargs: dict[str, Any],
) -> None:
    """Background task: dequeue the just-enqueued job and execute it."""
    item = jobs_module.dequeue_pick_run()
    if item is None:
        return
    dequeued_pick_id, dequeued_request, dequeued_kwargs, job_id = item
    success = _execute_pipeline_job(
        pick_id=dequeued_pick_id,
        request_dict=dequeued_request,
        bundle_kwargs=dequeued_kwargs,
    )
    if success:
        jobs_module.mark_job_done(job_id)
    else:
        jobs_module.mark_job_failed(job_id, "pipeline execution failed")


# --------------------------------------------------------------------------- #
# App factory                                                                 #
# --------------------------------------------------------------------------- #


def create_app() -> FastAPI:
    app = FastAPI(
        title="Colmillo-Picks API",
        version="0.2.0",
        description="HTTP wrapper around the soccer prop pick pipeline.",
    )

    init_sentry_if_configured()

    logger = configure_json_logging()
    app.add_middleware(APIKeyAuthMiddleware)
    app.add_middleware(RequestLoggingMiddleware, logger=logger)

    cors_origins = _cors_origins()
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-API-Key", "X-Admin-API-Key", "X-Request-Id"],
            allow_credentials=False,
        )

    db_module.init_db()

    # ---- Health ----------------------------------------------------------- #
    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok", providers=_provider_status())

    # ---- Picks (async) ---------------------------------------------------- #
    @app.post("/picks", response_model=PickAcceptedResponse, status_code=202)
    def picks(payload: PicksRequest, background_tasks: BackgroundTasks) -> PickAcceptedResponse:
        if payload.use_llm and not payload.llm_provider:
            raise HTTPException(
                status_code=400,
                detail="llm_provider is required when use_llm is true.",
            )

        bundle_kwargs = dict(
            use_llm=payload.use_llm,
            llm_provider=payload.llm_provider,
            llm_model=payload.llm_model,
            allow_deterministic_fallback=payload.allow_deterministic_fallback,
            league=payload.league,
            fixture_provider_name=payload.fixture_provider,
            fixture_llm_provider=payload.fixture_llm_provider,
            fixture_llm_model=payload.fixture_llm_model,
            fixture_llm_base_url=payload.fixture_llm_base_url,
            availability_provider=payload.availability_provider,
        )
        # Validate provider configuration synchronously so callers get a 400
        # for missing credentials instead of an asynchronous "failed" row.
        try:
            build_dependency_bundle(**bundle_kwargs)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        request_dict = _build_request_dict(payload)
        row = db_module.create_pending_pick_run(request_payload=request_dict)
        jobs_module.enqueue_pick_run(
            pick_id=row.id,
            request_dict=request_dict,
            bundle_kwargs=bundle_kwargs,
        )
        if os.environ.get("COLMILLO_WORKER_MODE") != "external":
            background_tasks.add_task(
                _run_next_queued_job, row.id, request_dict, bundle_kwargs
            )
        return PickAcceptedResponse(
            id=row.id,
            status=db_module.PICK_STATUS_PENDING,
            created_at=row.created_at,
        )

    @app.get("/picks", response_model=PicksListResponse)
    def list_picks(
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> PicksListResponse:
        rows = db_module.list_pick_runs(limit=limit, offset=offset)
        return PicksListResponse(
            items=[_row_to_summary(row) for row in rows], limit=limit, offset=offset
        )

    @app.get("/picks/{pick_id}", response_model=PickDetailResponse)
    def get_pick(pick_id: str) -> PickDetailResponse:
        row = db_module.get_pick_run(pick_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Pick not found.")
        return _row_to_detail(row)

    @app.get("/picks/{pick_id}/status", response_model=PickStatusResponse)
    def get_pick_status(pick_id: str) -> PickStatusResponse:
        row = db_module.get_pick_run(pick_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Pick not found.")
        return PickStatusResponse(
            id=row.id,
            status=row.status,
            error_stage=row.error_stage,
            error_message=row.error_message,
            latency_ms=row.latency_ms,
        )

    # ---- Outcomes (Story 9) ---------------------------------------------- #
    def _to_outcome_response(row: db_module.PickOutcome) -> OutcomeResponse:
        return OutcomeResponse(
            id=row.id,
            pick_id=row.pick_id,
            rank=row.rank,
            player=row.player,
            market=row.market,
            result=row.result,
            recorded_at=row.recorded_at,
        )

    @app.post(
        "/picks/{pick_id}/outcomes",
        response_model=OutcomesResponse,
        status_code=201,
    )
    def post_outcomes(pick_id: str, payload: OutcomesRequest) -> OutcomesResponse:
        if db_module.get_pick_run(pick_id) is None:
            raise HTTPException(status_code=404, detail="Pick not found.")
        try:
            rows = db_module.record_outcomes(
                pick_id=pick_id,
                outcomes=[entry.model_dump() for entry in payload.outcomes],
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return OutcomesResponse(
            pick_id=pick_id,
            items=[_to_outcome_response(row) for row in rows],
        )

    @app.get("/picks/{pick_id}/outcomes", response_model=OutcomesResponse)
    def get_outcomes(pick_id: str) -> OutcomesResponse:
        if db_module.get_pick_run(pick_id) is None:
            raise HTTPException(status_code=404, detail="Pick not found.")
        rows = db_module.list_outcomes(pick_id)
        return OutcomesResponse(
            pick_id=pick_id,
            items=[_to_outcome_response(row) for row in rows],
        )

    @app.get("/stats/hit-rate", response_model=HitRateResponse)
    def get_hit_rate(since: datetime | None = Query(None)) -> HitRateResponse:
        summary = db_module.hit_rate_summary(since=since)
        return HitRateResponse(**summary)

    # ---- Admin (Story 10) ------------------------------------------------ #
    @app.get("/admin/stats")
    def admin_stats(request: Request) -> dict[str, Any]:
        # Auth/admin enforcement happens in APIKeyAuthMiddleware. The route
        # prefix ``/admin`` triggers the admin gate there.
        del request
        return db_module.operational_stats()

    return app


app = create_app()
