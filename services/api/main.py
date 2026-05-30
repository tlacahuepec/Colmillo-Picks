"""FastAPI application exposing the soccer pick pipeline over HTTP.

``POST /picks`` is async: it validates the request synchronously, persists a
``pending`` row, schedules a background task that runs the full pipeline, and
returns ``202`` immediately. Clients then poll ``GET /picks/{id}/status`` (or
``GET /picks/{id}`` for the full payload) to discover ``success`` / ``failed``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
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
from pipeline_runner import PipelineRunError  # noqa: E402
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
    """Request body for ``POST /picks`` (legacy match_query format)."""

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


class StructuredPicksRequest(BaseModel):
    """Request body for ``POST /picks`` (sport-aware structured format)."""

    sport: str = Field(..., description="Sport: soccer, basketball, baseball")
    event_date: str = Field(..., description="YYYY-MM-DD")
    home_team: str
    away_team: str
    markets: list[str] = Field(default_factory=list)
    top_n: int = Field(5, ge=1, le=5)
    league: str | None = None
    platform: str | None = None
    use_llm: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    fixture_provider: str | None = None
    fixture_llm_provider: str | None = None
    fixture_llm_model: str | None = None
    fixture_llm_base_url: str | None = None
    allow_deterministic_fallback: bool = False
    availability_provider: str | None = None


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
    error_details: dict[str, Any] | None = None  # Rich observability context for failures (Epic #219)


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
    sport: str | None = None


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
    error_details: dict[str, Any] | None = None  # Rich observability context for failures (Epic #219)
    request: dict[str, Any]
    report_markdown: str
    scores: list[dict[str, Any]]
    trace: dict[str, Any] | None = None
    sport: str | None = None
    league: str | None = None
    markets: list[str] | None = None


class HealthResponse(BaseModel):
    status: str
    providers: dict[str, bool]
    version: str = "0.0.0-dev"
    commit: str = "unknown"
    build_time: str = "unknown"
    channel: str = "dev"


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


class AvailabilityCheckRequest(BaseModel):
    platforms: list[str] = Field(default_factory=lambda: ["prizepicks"])


class AvailabilityBadge(BaseModel):
    player: str
    market: str
    line: float
    status: str
    platform: str
    platform_line: float | None = None
    url: str | None = None
    last_checked: str


class AvailabilityCheckResponse(BaseModel):
    pick_id: str
    badges: list[AvailabilityBadge]
    fallback_mode: bool
    fallback_reason: str
    checked_at: str


class MatchDiscoveryRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD date to discover matches for.")
    sports: list[str] = Field(default_factory=lambda: ["soccer"], min_length=1)
    limit_per_sport: int = Field(5, ge=1, le=5)
    llm_provider: str | None = Field(None, description="gemini | grok | openai")
    llm_model: str | None = None


class DiscoverySource(BaseModel):
    label: str
    url: str | None = None


class DiscoveredMatch(BaseModel):
    sport: str
    home_team: str
    away_team: str
    event_date: str
    league: str | None = None
    competition: str | None = None
    kickoff_utc: str | None = None
    importance: str
    notes: str | None = None
    source_provider: str | None = None
    source_model: str | None = None
    sources: list[DiscoverySource] = Field(default_factory=list)
    data_quality: dict[str, Any] = Field(default_factory=dict)


class SportDiscoveryResult(BaseModel):
    matches: list[DiscoveredMatch] = Field(default_factory=list)
    error: str | None = None
    data_quality: dict[str, Any] = Field(default_factory=dict)


class MatchDiscoveryResponse(BaseModel):
    date_utc: str
    generated_at_utc: str
    limit_per_sport: int
    results: dict[str, SportDiscoveryResult]


class RunSummary(BaseModel):
    """Lightweight row used by ``GET /runs`` listings."""

    id: str
    source: str
    match_query: str
    competition: str | None = None
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    error_stage: str | None = None


class RunsListResponse(BaseModel):
    items: list[RunSummary]
    limit: int
    offset: int


class RunStepDetail(BaseModel):
    step_name: str
    status: str
    duration_ms: int


class RunPickDetail(BaseModel):
    rank: int
    player: str
    team_id: str
    market: str
    direction: str
    line: float
    score: float
    confidence: str
    risk_notes: list[str]


class RunDetailResponse(BaseModel):
    id: str
    source: str
    match_query: str
    competition: str | None = None
    status: str
    error_summary: str | None = None
    error_stage: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    steps: list[RunStepDetail]
    picks: list[RunPickDetail]


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _check_availability_for_picks(
    scores: list[dict[str, Any]], platforms: list[str]
) -> list[AvailabilityBadge]:
    from availability.mock_adapter import DeterministicMockAvailabilityAdapter

    adapter = DeterministicMockAvailabilityAdapter()
    platform_name = platforms[0] if platforms else "mock"

    badges: list[AvailabilityBadge] = []
    for pick in scores:
        player = pick.get("player", "")
        market = pick.get("market", "")
        line = pick.get("line", 0.0)
        if not player or not market:
            continue
        result = adapter.check_availability(player, market, line)
        if result.available:
            status = "available"
        else:
            status = "unavailable"
        badges.append(
            AvailabilityBadge(
                player=player,
                market=market,
                line=line,
                status=status,
                platform=platform_name,
                platform_line=None,
                url=result.url,
                last_checked=result.last_checked.isoformat(),
            )
        )
    return badges


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
        sport=getattr(row, "sport", None),
        # error_details not in summary for now, but available in detail/status
    )


def _row_to_detail(row: db_module.PickRun) -> PickDetailResponse:
    import json
    error_details = None
    if getattr(row, "error_details_json", None):
        try:
            error_details = json.loads(row.error_details_json)
        except Exception:
            error_details = None
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
        error_details=error_details,
        request=json.loads(row.request_json) if row.request_json else {},
        report_markdown=row.report_markdown or "",
        scores=json.loads(row.scores_json) if row.scores_json else [],
        trace=json.loads(row.trace_json) if row.trace_json else None,
        sport=getattr(row, "sport", None),
        league=getattr(row, "league", None),
        markets=json.loads(row.markets_json) if getattr(row, "markets_json", None) else None,
    )


def _build_run_ledger():
    from run_ledger import InMemoryRunLedger, SqliteRunLedger
    try:
        return SqliteRunLedger()
    except Exception:
        return InMemoryRunLedger()


def _build_match_discovery_client(payload: MatchDiscoveryRequest):
    from match_discovery import MatchDiscoveryClient

    return MatchDiscoveryClient.from_env(
        provider=payload.llm_provider,
        model=payload.llm_model,
    )


def _handle_legacy_picks(body: dict[str, Any], background_tasks: Any) -> PickAcceptedResponse:
    from pydantic import ValidationError as PydanticValidationError

    try:
        payload = PicksRequest(**body)
    except PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

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


def _handle_structured_picks(body: dict[str, Any], background_tasks: Any) -> PickAcceptedResponse:
    from pydantic import ValidationError as PydanticValidationError

    from pick_request import (
        PickRequest,
        PickRequestValidationError,
        pick_request_to_legacy_dict,
        validate_pick_request,
        SPORT_MARKETS,
    )

    try:
        payload = StructuredPicksRequest(**body)
    except PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    markets = tuple(payload.markets) if payload.markets else tuple(SPORT_MARKETS.get(payload.sport, ()))

    pick_req = PickRequest(
        sport=payload.sport,
        event_date=payload.event_date,
        home_team=payload.home_team,
        away_team=payload.away_team,
        markets=markets,
        top_n=payload.top_n,
        league=payload.league,
        platform=payload.platform,
        use_llm=payload.use_llm,
        llm_provider=payload.llm_provider,
        llm_model=payload.llm_model,
    )

    try:
        validate_pick_request(pick_req)
    except PickRequestValidationError as exc:
        raise HTTPException(status_code=400, detail="; ".join(exc.errors)) from exc

    if pick_req.sport != "soccer":
        from sport_module import get_sport_module, UnsupportedSportError

        try:
            get_sport_module(pick_req.sport)
        except UnsupportedSportError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        request_dict = {
            "_sport_module_path": True,
            "sport": pick_req.sport,
            "home_team": pick_req.home_team,
            "away_team": pick_req.away_team,
            "event_date": pick_req.event_date,
            "markets": list(pick_req.markets),
            "top_n": pick_req.top_n,
            "league": pick_req.league,
        }
        row = db_module.create_pending_pick_run(request_payload=request_dict)
        bundle_kwargs: dict[str, Any] = {}
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
    try:
        build_dependency_bundle(**bundle_kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    request_dict = pick_request_to_legacy_dict(pick_req)
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


def _run_sport_module_pipeline(request_dict: dict[str, Any]) -> dict[str, Any]:
    """Execute non-soccer sports via PipelineRunner + SportModule."""
    from pick_request import PickRequest
    from pipeline_runner import PipelineRunner
    from sport_module import get_sport_module

    sport = request_dict.get("sport", "basketball")
    module = get_sport_module(sport)
    markets = tuple(request_dict.get("markets", ()))
    pick_req = PickRequest(
        sport=sport,
        event_date=request_dict.get("event_date", ""),
        home_team=request_dict.get("home_team", ""),
        away_team=request_dict.get("away_team", ""),
        markets=markets if markets else tuple(module.supported_markets),
        top_n=request_dict.get("top_n", 5),
        league=request_dict.get("league"),
    )
    runner = PipelineRunner()
    pipeline_result = runner.run(request=pick_req, module=module)

    report_md = _render_report_for_sport(
        sport=sport,
        scores=pipeline_result.scores,
        match_inputs=pipeline_result.match_inputs,
    )
    trace = _build_trace_for_sport(
        sport=sport,
        scores=pipeline_result.scores,
        match_inputs=pipeline_result.match_inputs,
        steps=pipeline_result.steps,
    )

    return {
        "scores": pipeline_result.scores,
        "match_inputs": pipeline_result.match_inputs,
        "steps": pipeline_result.steps,
        "report_markdown": report_md,
        "trace": trace,
    }


def _render_report_for_sport(
    sport: str, scores: list[dict[str, Any]], match_inputs: dict[str, Any]
) -> str:
    if sport == "baseball":
        from render_baseball_report import render_baseball_report

        return render_baseball_report(
            match_context=match_inputs,
            picks=scores,
            no_bet_picks=match_inputs.get("no_bet_picks"),
            provider_statuses=match_inputs.get("provider_statuses"),
        )

    from render_basketball_report import render_basketball_report

    used_fallback = not match_inputs.get("game")
    return render_basketball_report(
        scores,
        match_inputs,
        used_fallback=used_fallback,
    )


def _build_trace_for_sport(
    sport: str,
    scores: list[dict[str, Any]],
    match_inputs: dict[str, Any],
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    if sport == "baseball":
        from baseball_trace import MLBTraceRecord, PickTrace, compute_input_hash

        picks = [
            PickTrace(
                player=s.get("player", "Unknown"),
                market=s.get("market", "unknown"),
                direction=s.get("direction", "over"),
                line=s.get("line", 0),
                score=s.get("score", 0),
                confidence=s.get("confidence", "medium"),
                risk_flags=s.get("explainability", {}).get("risk_flags", []),
                top_factors=s.get("explainability", {}).get("top_contributing_factors", []),
            )
            for s in scores
        ]
        record = MLBTraceRecord(
            run_id=match_inputs.get("run_id", ""),
            input_hash=compute_input_hash(match_inputs),
            picks=picks,
        )
        return record.model_dump()

    used_fallback = not match_inputs.get("game")
    return {
        "llm_status": "fallback" if used_fallback else "completed",
        "pipeline_steps": steps,
    }


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
        if request_dict.get("_sport_module_path"):
            result = _run_sport_module_pipeline(request_dict)
        else:
            deps = build_dependency_bundle(**bundle_kwargs)
            result = run_pipeline_with_payload(request=request_dict, deps=deps)
    except PipelineRunError as exc:
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        error_details = getattr(exc, "error_details", None)
        db_module.mark_pick_failed(
            pick_id=pick_id,
            stage=exc.stage,
            message=exc.message,
            latency_ms=latency_ms,
            error_details=error_details,
        )
        provider_status = (error_details or {}).get("provider_status") or None
        ledger.fail_run(
            run_ctx.id,
            error_summary=exc.message,
            error_stage=exc.stage,
            provider_status=provider_status,
        )

        # Structured observability log for failures (Epic #219)
        try:
            logger = logging.getLogger("colmillo")
            log_extra = {
                "sport": request_dict.get("sport"),
                "stage": exc.stage,
                "home_team": request_dict.get("home_team"),
                "away_team": request_dict.get("away_team"),
                "match_date": request_dict.get("event_date") or request_dict.get("match_date"),
                "error_summary": exc.message,
                "critical_missing_fields": (error_details or {}).get("critical_missing_fields"),
                "provider_status_summary": (error_details or {}).get("provider_status"),
            }
            logger.warning("pipeline_run_failed", extra={k: v for k, v in log_extra.items() if v is not None})
        except Exception:
            pass  # logging must never break the failure path

        return False
    except PipelineServiceError as exc:
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        cause = exc.__cause__
        message = str(cause) if cause else str(exc)
        error_details = getattr(exc, "error_details", None)
        db_module.mark_pick_failed(
            pick_id=pick_id, stage=exc.stage, message=message, latency_ms=latency_ms, error_details=error_details
        )
        provider_status = (error_details or {}).get("provider_status") if error_details else None
        ledger.fail_run(run_ctx.id, error_summary=message, error_stage=exc.stage, provider_status=provider_status)
        return False
    except Exception as exc:  # configuration / unexpected errors
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        error_details = getattr(exc, "error_details", None)
        db_module.mark_pick_failed(
            pick_id=pick_id, stage="unknown", message=str(exc), latency_ms=latency_ms, error_details=error_details
        )
        provider_status = (error_details or {}).get("provider_status") if error_details else None
        ledger.fail_run(run_ctx.id, error_summary=str(exc), error_stage="unknown", provider_status=provider_status)
        # Log unexpected errors with any available context
        try:
            logger = logging.getLogger("colmillo")
            logger.error("unexpected_pipeline_error", extra={"error": str(exc), "error_details": error_details})
        except Exception:
            pass
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
        from app_metadata import get_app_metadata
        meta = get_app_metadata()
        return HealthResponse(
            status="ok",
            providers=_provider_status(),
            version=meta.version,
            commit=meta.commit,
            build_time=meta.build_time,
            channel=meta.channel,
        )

    @app.get("/version")
    def version() -> dict:
        from app_metadata import get_app_metadata
        meta = get_app_metadata()
        return {
            "version": meta.version,
            "commit": meta.commit,
            "build_time": meta.build_time,
            "branch": meta.branch,
            "channel": meta.channel,
        }

    # ---- Match Discovery ------------------------------------------------- #
    @app.post("/matches/discover", response_model=MatchDiscoveryResponse)
    def discover_matches(payload: MatchDiscoveryRequest) -> MatchDiscoveryResponse:
        from match_discovery import (
            MatchDiscoveryError,
            MatchDiscoveryValidationError,
            validate_match_discovery_inputs,
        )

        try:
            sports = validate_match_discovery_inputs(
                date_utc=payload.date,
                sports=payload.sports,
                limit_per_sport=payload.limit_per_sport,
            )
            client = _build_match_discovery_client(payload)
            result = client.discover_matches(
                date_utc=payload.date,
                sports=sports,
                limit_per_sport=payload.limit_per_sport,
            )
        except MatchDiscoveryValidationError as exc:
            raise HTTPException(status_code=400, detail="; ".join(exc.errors)) from exc
        except MatchDiscoveryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return MatchDiscoveryResponse(**result)

    # ---- Picks (async) ---------------------------------------------------- #
    @app.post("/picks", response_model=PickAcceptedResponse, status_code=202)
    async def picks(request: Request, background_tasks: BackgroundTasks) -> PickAcceptedResponse:
        body = await request.json()

        if "sport" in body:
            return _handle_structured_picks(body, background_tasks)
        return _handle_legacy_picks(body, background_tasks)

    @app.get("/picks", response_model=PicksListResponse)
    def list_picks(
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        sport: str | None = Query(None),
    ) -> PicksListResponse:
        rows = db_module.list_pick_runs(limit=limit, offset=offset, sport=sport)
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
        import json
        error_details = None
        if getattr(row, "error_details_json", None):
            try:
                error_details = json.loads(row.error_details_json)
            except Exception:
                error_details = None
        return PickStatusResponse(
            id=row.id,
            status=row.status,
            error_stage=row.error_stage,
            error_message=row.error_message,
            latency_ms=row.latency_ms,
            error_details=error_details,
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

    # ---- Availability (Issue #62) ---------------------------------------- #

    @app.post(
        "/picks/{pick_id}/availability",
        response_model=AvailabilityCheckResponse,
    )
    def check_availability(pick_id: str, payload: AvailabilityCheckRequest) -> AvailabilityCheckResponse:
        pick_run = db_module.get_pick_run(pick_id)
        if pick_run is None:
            raise HTTPException(status_code=404, detail="Pick not found.")

        scores = json.loads(pick_run.scores_json) if pick_run.scores_json else []
        if not scores:
            return AvailabilityCheckResponse(
                pick_id=pick_id,
                badges=[],
                fallback_mode=True,
                fallback_reason="No scores available for this pick.",
                checked_at=datetime.now(timezone.utc).isoformat(),
            )

        try:
            badges = _check_availability_for_picks(scores, payload.platforms)
        except Exception as exc:
            return AvailabilityCheckResponse(
                pick_id=pick_id,
                badges=[],
                fallback_mode=True,
                fallback_reason=f"Adapter error: {exc}",
                checked_at=datetime.now(timezone.utc).isoformat(),
            )

        return AvailabilityCheckResponse(
            pick_id=pick_id,
            badges=badges,
            fallback_mode=False,
            fallback_reason="",
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

    # ---- Admin (Story 10) ------------------------------------------------ #
    @app.get("/admin/stats")
    def admin_stats(request: Request) -> dict[str, Any]:
        # Auth/admin enforcement happens in APIKeyAuthMiddleware. The route
        # prefix ``/admin`` triggers the admin gate there.
        del request
        return db_module.operational_stats()

    # ---- Run History (Story 12) ------------------------------------------ #
    @app.get("/runs", response_model=RunsListResponse)
    def list_runs(
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> RunsListResponse:
        ledger = _build_run_ledger()
        runs = ledger.list_runs(limit=limit, offset=offset)
        return RunsListResponse(
            items=[
                RunSummary(
                    id=r.id,
                    source=r.source,
                    match_query=r.match_query,
                    competition=r.competition,
                    status=r.status,
                    started_at=r.started_at,
                    completed_at=r.completed_at,
                    duration_ms=r.duration_ms,
                    error_stage=r.error_stage,
                )
                for r in runs
            ],
            limit=limit,
            offset=offset,
        )

    @app.get("/runs/{run_id}", response_model=RunDetailResponse)
    def get_run(run_id: str) -> RunDetailResponse:
        ledger = _build_run_ledger()
        run = ledger.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found.")
        steps = ledger.get_steps(run_id)
        picks = ledger.get_picks(run_id)
        return RunDetailResponse(
            id=run.id,
            source=run.source,
            match_query=run.match_query,
            competition=run.competition,
            status=run.status,
            error_summary=run.error_summary,
            error_stage=run.error_stage,
            started_at=run.started_at,
            completed_at=run.completed_at,
            duration_ms=run.duration_ms,
            steps=[
                RunStepDetail(step_name=s.step_name, status=s.status, duration_ms=s.duration_ms)
                for s in steps
            ],
            picks=[
                RunPickDetail(
                    rank=p.rank, player=p.player, team_id=p.team_id,
                    market=p.market, direction=p.direction, line=p.line,
                    score=p.score, confidence=p.confidence, risk_notes=p.risk_notes,
                )
                for p in picks
            ],
        )

    return app


app = create_app()
