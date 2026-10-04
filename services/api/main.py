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
from services.api.enrichment_audit import (  # noqa: E402
    EnrichmentAuditRequest,
    EnrichmentAuditResponse,
    execute_enrichment_audit,
)
from services.api import jobs as jobs_module  # noqa: E402
from services.api.logging_config import configure_json_logging  # noqa: E402
from services.api.middleware import (  # noqa: E402
    APIKeyAuthMiddleware,
    RequestLoggingMiddleware,
)
from services.api.sentry import init_sentry_if_configured  # noqa: E402
from services.catalog.refresh import run_fanatics_refresh, start_fanatics_refresh  # noqa: E402
from services.catalog.storage import CatalogStore  # noqa: E402
from services.diagnostics import emit, error_info, finish_operation, instrument, operation, public_trace  # noqa: E402


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #


class PicksRequest(BaseModel):
    """Request body for ``POST /picks`` (legacy match_query format)."""

    match_query: str = Field(..., description="e.g. 'arsenal - liverpool 2026-05-03'")
    top_n: int = Field(10, ge=1, le=10)
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


class CatalogRefreshRequest(BaseModel):
    """Request one bounded catalog refresh for a calendar day."""

    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")


class CatalogSportSettingsRequest(BaseModel):
    """Persistent visibility policy for a discovered catalog sport."""

    enabled: bool


class StructuredPicksRequest(BaseModel):
    """Request body for ``POST /picks`` (sport-aware structured format)."""

    sport: str = Field(..., description="Sport: soccer, basketball, baseball, nfl")
    timezone: str | None = Field(None, description="IANA timezone for NFL event_date; defaults to COLMILLO_TIMEZONE or America/Chicago")
    event_date: str = Field(..., description="YYYY-MM-DD")
    home_team: str
    away_team: str
    markets: list[str] = Field(default_factory=list)
    top_n: int = Field(10, ge=1, le=10)
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


class DiagnosticReference(BaseModel):
    operation_id: str | None = None
    outcome: str | None = None


class PickAcceptedResponse(DiagnosticReference):
    """Body of the ``202`` returned by ``POST /picks``."""

    id: str
    status: str
    created_at: datetime


class PickStatusResponse(DiagnosticReference):
    id: str
    status: str
    error_stage: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    error_details: dict[str, Any] | None = None  # Rich observability context for failures (Epic #219)


class PickSummary(DiagnosticReference):
    """Lightweight row used by ``GET /picks`` listings."""

    id: str
    created_at: datetime
    match_query: str
    display_title: str
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


class PickDetailResponse(DiagnosticReference):
    id: str
    created_at: datetime
    match_query: str
    display_title: str
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


class BatchAvailabilityRequest(BaseModel):
    candidates: list[dict[str, Any]] = Field(..., min_length=1)
    platforms: list[str] = Field(default_factory=lambda: ["prizepicks"])


class BatchAvailabilityResponse(BaseModel):
    badges: list[AvailabilityBadge]
    fallback_mode: bool
    fallback_reason: str
    checked_at: str


class MatchDiscoveryRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD date to discover matches for.")
    sports: list[str] = Field(default_factory=lambda: ["soccer"], min_length=1)
    limit_per_sport: int = Field(5, ge=1, le=10)
    llm_provider: str | None = Field(None, description="gemini | grok | openai")
    llm_model: str | None = None
    timezone: str | None = Field(None, description="IANA timezone for date filtering (e.g., America/Chicago)")
    force_refresh: bool = Field(False, description="Bypass a still-valid cached discovery result.")


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
    cache_status: str | None = None
    cache_confidence: str | None = None
    cache_expires_at: str | None = None


class SlateRequest(BaseModel):
    """Request body for ``POST /slates``."""

    nfl_market_group: Literal["all", "player_props", "game_bets"] = "all"

    date: str = Field(..., description="YYYY-MM-DD")
    sports: list[str] = Field(
        default_factory=lambda: ["soccer", "basketball", "baseball", "nfl"], min_length=1
    )
    max_matches_per_sport: int = Field(3, ge=1, le=5)
    top_n: int = Field(10, ge=1, le=20)
    llm_provider: str | None = None
    llm_model: str | None = None
    timezone: str | None = Field(None, description="IANA timezone for date filtering (e.g., America/Chicago)")


class SlateAcceptedResponse(DiagnosticReference):
    id: str
    status: str
    created_at: datetime


class SlateStatusResponse(DiagnosticReference):
    id: str
    status: str
    error_stage: str | None = None
    error_message: str | None = None
    latency_ms: int | None = None
    progress_stage: str | None = None
    matches_discovered: int | None = None
    matches_completed: int | None = None
    heartbeat_at: datetime | None = None
    stop_reason: str | None = None
    resume_count: int = 0


class SlateSummary(DiagnosticReference):
    id: str
    created_at: datetime
    status: str
    request: dict[str, Any]
    latency_ms: int | None = None
    progress_stage: str | None = None
    matches_discovered: int | None = None
    matches_completed: int | None = None
    heartbeat_at: datetime | None = None
    stop_reason: str | None = None


class SlateListResponse(BaseModel):
    items: list[SlateSummary]
    limit: int
    offset: int


class SlateMatchRunSummary(BaseModel):
    sport: str
    home_team: str = ""
    away_team: str = ""
    event_date: str = ""
    status: str
    error_stage: str | None = None
    error_message: str | None = None
    pick_count: int = 0
    latency_ms: int | None = None


class SlateRankedCandidate(BaseModel):
    rank: int = 0
    sport: str
    player: str
    subject_type: str = "player"
    subject_name: str = ""
    selection: str = ""
    offer: dict[str, Any] | None = None
    market: str
    line: Any = None
    direction: str
    confidence: str
    normalized_score: float
    risk_flags: list[str] = Field(default_factory=list)
    availability_status: str = "unknown"
    source_match: dict[str, Any] = Field(default_factory=dict)
    source_pick: dict[str, Any] = Field(default_factory=dict)


class SlateDetailResponse(DiagnosticReference):
    id: str
    created_at: datetime
    status: str
    request: dict[str, Any]
    candidates: list[SlateRankedCandidate] = Field(default_factory=list)
    match_runs: list[SlateMatchRunSummary] = Field(default_factory=list)
    matches_attempted: int | None = None
    matches_succeeded: int | None = None
    latency_ms: int | None = None
    discovery_latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    error_stage: str | None = None
    error_message: str | None = None
    progress_stage: str | None = None
    matches_discovered: int | None = None
    matches_completed: int | None = None
    heartbeat_at: datetime | None = None
    stop_reason: str | None = None
    resume_count: int = 0


class RunSummary(DiagnosticReference):
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
    line: float | None
    score: float
    confidence: str
    risk_notes: list[str]
    source_pick: dict[str, Any] = Field(default_factory=dict)


class RunDetailResponse(DiagnosticReference):
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


@instrument("availability")
def _check_availability_for_picks(
    scores: list[dict[str, Any]], platforms: list[str]
) -> list[AvailabilityBadge]:
    from availability.mock_adapter import DeterministicMockAvailabilityAdapter

    adapter = DeterministicMockAvailabilityAdapter()
    platform_name = platforms[0] if platforms else "mock"

    badges: list[AvailabilityBadge] = []
    for pick in scores:
        if pick.get("subject_type", "player") != "player":
            continue
        player = pick.get("player", "")
        market = pick.get("market", "")
        line = pick.get("line", 0.0)
        if not player or not market:
            continue
        if pick.get("sport") == "nfl":
            if line is not None:
                badges.append(AvailabilityBadge(
                    player=player, market=market, line=line, status="unknown",
                    platform=platform_name, last_checked=datetime.now(timezone.utc).isoformat(),
                ))
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


def _display_pick_title(row: db_module.PickRun) -> str:
    """Return a stable, customer-facing label without rewriting the raw query.

    Older structured runs did not persist ``match_query``. Their submitted
    teams and date are still available in ``request_json``, so derive a display
    label at read time while leaving the original request intact.
    """
    raw_query = (row.match_query or "").strip()
    if raw_query:
        return raw_query

    try:
        request = json.loads(row.request_json) if row.request_json else {}
    except (TypeError, json.JSONDecodeError):
        request = {}

    def text_value(key: str) -> str:
        value = request.get(key)
        return value.strip() if isinstance(value, str) else ""

    home_team = text_value("home_team")
    away_team = text_value("away_team")
    event_date = text_value("event_date")
    if home_team and away_team:
        matchup = f"{home_team} vs {away_team}"
        return f"{matchup} · {event_date}" if event_date else matchup

    sport = (getattr(row, "sport", None) or text_value("sport") or "Pick").strip()
    title = f"{sport.title()} run"
    if event_date:
        title = f"{title} · {event_date}"
    return f"{title} · {row.id[:8]}"


def _row_to_summary(row: db_module.PickRun) -> PickSummary:
    return PickSummary(
        operation_id=getattr(row, "operation_id", None),
        outcome=getattr(row, "outcome", None),
        id=row.id,
        created_at=row.created_at,
        match_query=row.match_query,
        display_title=_display_pick_title(row),
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
    if row.error_details_json:
        try:
            error_details = json.loads(row.error_details_json)
        except Exception:
            error_details = None
    safe_error_details = public_trace(error_details)
    safe_trace = public_trace(json.loads(row.trace_json)) if row.trace_json else None
    return PickDetailResponse(
        operation_id=getattr(row, "operation_id", None),
        outcome=getattr(row, "outcome", None),
        id=row.id,
        created_at=row.created_at,
        match_query=row.match_query,
        display_title=_display_pick_title(row),
        competition=row.competition,
        top_n=row.top_n,
        status=row.status,
        fixture_status=row.fixture_status,
        llm_status=row.llm_status,
        latency_ms=row.latency_ms,
        error_stage=row.error_stage,
        error_message=row.error_message,
        error_details=safe_error_details if isinstance(safe_error_details, dict) else None,
        request=json.loads(row.request_json) if row.request_json else {},
        report_markdown=row.report_markdown or "",
        scores=json.loads(row.scores_json) if row.scores_json else [],
        trace=safe_trace if isinstance(safe_trace, dict) else None,
        sport=getattr(row, "sport", None),
        league=getattr(row, "league", None),
        markets=json.loads(row.markets_json) if row.markets_json else None,
    )


def _build_run_ledger():
    from run_ledger import InMemoryRunLedger, SqliteRunLedger
    try:
        return SqliteRunLedger()
    except Exception as exc:
        emit("ledger.unavailable", stage="save", level="WARNING", **error_info(exc))
        return InMemoryRunLedger()


def _discovery_cache_key(
    *, date: str, sports: list[str], limit: int, timezone_name: str | None = None,
    provider: str | None = None, model: str | None = None,
) -> str:
    sports_part = ":".join(sorted(sports))
    tz_part = timezone_name or "utc"
    provider_part = (provider or os.getenv("COLMILLO_LLM_PROVIDER") or "gemini").strip().lower()
    model_part = (model or "default").strip().lower()
    return f"discovery:v2:{date}:{sports_part}:{limit}:{tz_part}:{provider_part}:{model_part}"


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

    bundle_kwargs: dict[str, Any] = dict(
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
        operation_id=row.operation_id,
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
        if pick_req.sport == "nfl":
            request_dict.update(llm_provider=payload.llm_provider, llm_model=payload.llm_model, timezone=payload.timezone)
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
            operation_id=row.operation_id,
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
        league=pick_req.league,
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
        operation_id=row.operation_id,
        id=row.id,
        status=db_module.PICK_STATUS_PENDING,
        created_at=row.created_at,
    )


def _filter_zero_line_scores(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from nfl_domain import has_valid_pick_line
    return [s for s in scores if has_valid_pick_line(s)]


def _run_sport_module_pipeline(request_dict: dict[str, Any]) -> dict[str, Any]:
    """Execute non-soccer sports via PipelineRunner + SportModule."""
    from pick_request import PickRequest
    from pipeline_runner import PipelineRunner
    from sport_module import get_sport_module

    sport = request_dict.get("sport", "basketball")
    module = get_sport_module(sport)
    if sport == "nfl" and any(request_dict.get(k) for k in ("llm_provider", "llm_model", "timezone")):
        from nfl_module import NflModule
        module = NflModule(provider=request_dict.get("llm_provider"), model=request_dict.get("llm_model"), timezone_name=request_dict.get("timezone"))
    markets = tuple(request_dict.get("markets", ()))
    pick_req = PickRequest(
        sport=sport,
        event_date=request_dict.get("event_date", ""),
        home_team=request_dict.get("home_team", ""),
        away_team=request_dict.get("away_team", ""),
        markets=markets if markets else tuple(module.supported_markets),
        top_n=request_dict.get("top_n", 10),
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
        "outcome": getattr(pipeline_result, "outcome", None) or ("partial" if pipeline_result.scores and pipeline_result.match_inputs.get("provider_errors") else "success" if pipeline_result.scores else "no_picks"),
        "scores": _filter_zero_line_scores(pipeline_result.scores),
        "match_inputs": pipeline_result.match_inputs,
        "steps": pipeline_result.steps,
        "report_markdown": report_md,
        "trace": trace,
    }


def _render_report_for_sport(
    sport: str, scores: list[dict[str, Any]], match_inputs: dict[str, Any]
) -> str:
    if sport == "nfl":
        from render_nfl_report import render_nfl_report
        return render_nfl_report(scores, match_inputs)
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
    if sport == "nfl":
        return {"sport": "nfl", "steps": steps, "picks": scores,
                "exclusions": match_inputs.get("exclusions", []),
                "provider_statuses": match_inputs.get("provider_statuses", {}),
                "grounding_sources": match_inputs.get("grounding_sources", []),
                "provider_errors": match_inputs.get("provider_errors", {}),
                "recommendation_summary": match_inputs.get("recommendation_summary", {}),
                "research_evidence": match_inputs.get("research_evidence", {})}
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
    ident = request_dict.get("operation_id") or pick_id
    request_dict = {**request_dict, "operation_id": ident}
    with operation("generate", operation_id=ident, service="worker" if os.getenv("COLMILLO_WORKER_MODE") == "external" else "api",
                   pick_id=pick_id, **{k: request_dict[k] for k in ("request_id", "job_id", "sport", "home_team", "away_team", "event_date", "attempt", "queue_ms") if k in request_dict}) as diagnostic:
        success = _execute_pipeline_job_inner(pick_id=pick_id, request_dict=request_dict, bundle_kwargs=bundle_kwargs)
        outcome, summary = "success" if success else "failed", {}
        try:
            row = db_module.get_pick_run(pick_id)
            outcome = getattr(row, "outcome", None) or outcome
            summary = json.loads(row.diagnostics_json) if row and row.diagnostics_json else {}
            if not isinstance(summary, dict):
                summary = {}
        except Exception as exc:
            emit("diagnostics.summary_unavailable", level="WARNING", **error_info(exc))
        diagnostic.finish(outcome, **{k: v for k, v in summary.items() if k not in {"outcome", "summary"}})
        return success


def _execute_pipeline_job_inner(*, pick_id: str, request_dict: dict[str, Any], bundle_kwargs: dict[str, Any]) -> bool:
    """Background task body: run the pipeline and update the pending row."""
    ledger = _build_run_ledger()
    run_ctx = ledger.start_run(source="api", request=request_dict)
    emit("ledger.started", run_id=run_ctx.id)

    started = time.perf_counter()
    try:
        if request_dict.get("_sport_module_path"):
            result = _run_sport_module_pipeline(request_dict)
        else:
            deps = build_dependency_bundle(**bundle_kwargs)
            result = run_pipeline_with_payload(request=request_dict, deps=deps)
    except PipelineRunError as exc:
        diagnostic_error = error_info(exc)
        emit("pipeline.failed", stage=exc.stage, level="ERROR", **diagnostic_error)
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        error_details = {**diagnostic_error, **(getattr(exc, "error_details", None) or {})}
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
        emit("pipeline.failed", stage=exc.stage, level="ERROR", **error_info(exc))
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        cause = exc.__cause__
        message = str(cause) if cause else str(exc)
        error_details = {**error_info(exc), **(getattr(exc, "error_details", None) or {})}
        db_module.mark_pick_failed(
            pick_id=pick_id, stage=exc.stage, message=message, latency_ms=latency_ms, error_details=error_details
        )
        provider_status = (error_details or {}).get("provider_status") if error_details else None
        ledger.fail_run(run_ctx.id, error_summary=message, error_stage=exc.stage, provider_status=provider_status)
        return False
    except Exception as exc:  # configuration / unexpected errors
        emit("pipeline.failed", level="ERROR", **error_info(exc))
        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        error_details = {**error_info(exc), **(getattr(exc, "error_details", None) or {})}
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
    if request_dict.get("_sport_module_path") and "scores" in result:
        result["scores"] = _filter_zero_line_scores(result["scores"])

    try:
        db_module.mark_pick_success(pick_id=pick_id, result=result, latency_ms=latency_ms)
    except Exception as exc:
        _logger = logging.getLogger("colmillo")
        _logger.error("mark_pick_success_failed", extra={"pick_id": pick_id, "error": str(exc)})
        emit("persistence.failed", stage="save", level="ERROR", **error_info(exc))
        ledger.fail_run(run_ctx.id, error_summary=f"post-success persistence: {exc}", error_stage="persistence")
        return False

    try:
        for step in result.get("steps", []):
            ledger.record_step(run_ctx.id, step["name"], status=step["status"], duration_ms=step["duration_ms"])
        ledger.save_picks(run_ctx.id, result.get("scores", []))
        failed_steps = [s for s in result.get("steps", []) if s["status"] == "failed"]
        if failed_steps or result.get("outcome") == "partial":
            reasons = [f"{s['name']} failed" for s in failed_steps]
            if not reasons:
                reasons = ["Some provider inputs were unavailable."]
            ledger.partial_run(run_ctx.id, reasons=reasons)
        else:
            ledger.complete_run(run_ctx.id, outcome="success" if result.get("scores") else "no_picks")
    except Exception as exc:
        _logger = logging.getLogger("colmillo")
        _logger.error("ledger_post_success_failed", extra={"pick_id": pick_id, "error": str(exc)})
        emit("ledger.failed", stage="save", level="ERROR", **error_info(exc))

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


def _run_next_queued_slate_job() -> None:
    """Background task: dequeue and execute the next queued slate job."""
    item = jobs_module.dequeue_slate_run()
    if item is None:
        return
    slate_id, request_dict, job_id = item
    with operation("slate", operation_id=request_dict.get("operation_id") or slate_id,
                   slate_id=slate_id, job_id=job_id,
                   **{k: request_dict[k] for k in ("request_id", "attempt", "queue_ms") if k in request_dict}) as diagnostic:
        _execute_slate_record(slate_id, request_dict, job_id)
        row = db_module.get_slate_run(slate_id)
        diagnostic.finish(getattr(row, "outcome", None) or "failed")


def _serialize_slate_candidates(candidates):
    return [
        {
            "rank": idx + 1, "sport": candidate.sport, "player": candidate.player,
            "subject_type": candidate.subject_type, "subject_name": candidate.subject_name,
            "selection": candidate.selection, "offer": candidate.offer, "market": candidate.market,
            "line": candidate.line, "direction": candidate.direction, "confidence": candidate.confidence,
            "normalized_score": candidate.normalized_score, "risk_flags": list(candidate.risk_flags),
            "availability_status": candidate.availability_status, "source_match": candidate.source_match,
            "source_pick": dict(candidate.source_pick) if candidate.source_pick else {},
        }
        for idx, candidate in enumerate(candidates)
    ]


def _restore_slate_candidates(records):
    from slate_ranking import SlateCandidate
    restored = []
    for record in records:
        if not isinstance(record, dict):
            continue
        try:
            restored.append(SlateCandidate(
                sport=record["sport"], source_match=record.get("source_match") or {}, player=record["player"],
                market=record["market"], line=record.get("line"), direction=record["direction"],
                confidence=record["confidence"], raw_score=None, normalized_score=float(record["normalized_score"]),
                risk_flags=tuple(record.get("risk_flags") or ()), availability_status=record.get("availability_status", "unknown"),
                source_pick=record.get("source_pick") or {}, subject_type=record.get("subject_type", "player"),
                subject_name=record.get("subject_name", ""), selection=record.get("selection", ""), offer=record.get("offer"),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return restored


def _execute_slate_record(slate_id, request_dict, job_id):

    from services.api.slate_orchestration import (
        execute_slate_job,
    )

    try:
        deps = _build_slate_deps(request_dict)
        existing_row = db_module.get_slate_run(slate_id)
        resume_kwargs = {}
        if request_dict.get("_resume") and existing_row is not None:
            resume_kwargs = {
                "discovery_override": json.loads(existing_row.discovered_matches_json or "[]"),
                "existing_match_runs": json.loads(existing_row.match_runs_json or "[]"),
                "existing_candidates": _restore_slate_candidates(json.loads(existing_row.candidates_json or "[]")),
            }
        def checkpoint(stage_name, discovered_matches, candidates, match_runs, discovery_latency_ms):
            db_module.checkpoint_slate_run(
                slate_id=slate_id, stage=stage_name, discovered_matches=discovered_matches,
                candidates=_serialize_slate_candidates(candidates), match_runs=match_runs,
                discovery_latency_ms=discovery_latency_ms,
            )
            jobs_module.heartbeat_slate_job(job_id)

        result = execute_slate_job(request_dict=request_dict, deps=deps, on_checkpoint=checkpoint, **resume_kwargs)
        candidates_dicts = _serialize_slate_candidates(result.candidates)

        if result.interrupted:
            db_module.mark_slate_interrupted(
                slate_id=slate_id, reason=result.stop_reason or "budget_exhausted",
                message="Slate execution reached its configured time budget. Resume to run remaining matches.",
                latency_ms=result.latency_ms, candidates=candidates_dicts, match_runs=result.match_runs,
                discovered_matches=result.discovered_matches or [], discovery_latency_ms=result.discovery_latency_ms,
                prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
            )
            jobs_module.mark_slate_job_failed(job_id, "Slate interrupted; customer resume required")
            return

        if not result.candidates and (getattr(result, "discovery_failures", 0) or any(m.get("status") in {"failed", "pending_data"} for m in result.match_runs)):
            db_module.mark_slate_failed(
                slate_id=slate_id,
                stage="aggregation",
                message=f"No viable candidates produced from {result.matches_attempted} attempted matches",
                latency_ms=result.latency_ms,
                candidates=candidates_dicts,
                match_runs=result.match_runs,
                discovery_latency_ms=result.discovery_latency_ms,
                matches_attempted=result.matches_attempted,
                matches_succeeded=result.matches_succeeded,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
            )
        else:
            db_module.mark_slate_success(
                slate_id=slate_id,
                candidates=candidates_dicts,
                match_runs=result.match_runs,
                latency_ms=result.latency_ms,
                discovery_latency_ms=result.discovery_latency_ms,
                matches_attempted=result.matches_attempted,
                matches_succeeded=result.matches_succeeded,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
                partial=bool(getattr(result, "discovery_failures", 0)),
            )
        row = db_module.get_slate_run(slate_id)
        if row and row.status == "failed":
            jobs_module.mark_slate_job_failed(job_id, "No viable results; see diagnostics.")
        else:
            jobs_module.mark_slate_job_done(job_id)
    except Exception as exc:
        emit("slate.failed", level="ERROR", **error_info(exc))
        db_module.mark_slate_failed(
            slate_id=slate_id,
            stage="discovery",
            message=str(exc)[:500],
            latency_ms=0,
        )
        jobs_module.mark_slate_job_failed(job_id, str(exc)[:500])


def _build_slate_deps(request_dict: dict[str, Any]):
    from match_discovery import MatchDiscoveryClient
    from services.api.slate_orchestration import SlateOrchestrationDeps
    from sport_module import get_sport_module

    max_output_tokens = 16000 if "nfl" in request_dict.get("sports", ["nfl"]) else 8192
    discovery_client = MatchDiscoveryClient.from_env(
        provider=request_dict.get("llm_provider"),
        model=request_dict.get("llm_model"),
        max_output_tokens=max_output_tokens,
    )

    def discover(*, date_utc: str, sports: list[str], limit_per_sport: int, timezone: str | None = None) -> dict[str, Any]:
        return discovery_client.discover_matches(
            date_utc=date_utc, sports=sports, limit_per_sport=limit_per_sport, timezone=timezone
        )

    def run_pipeline(
        *, sport: str, home_team: str, away_team: str, event_date: str, markets: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        with operation("slate_match", sport=sport, home_team=home_team, away_team=away_team,
                       event_date=event_date, parent_operation_id=request_dict.get("operation_id")) as diagnostic:
            try:
                scores = run_match(sport=sport, home_team=home_team, away_team=away_team, event_date=event_date, markets=markets)
            except Exception as exc:
                from nfl_module import NflNoPicks
                if isinstance(exc, NflNoPicks):
                    diagnostic.finish("no_picks")
                raise
            diagnostic.finish("success" if scores else "no_picks", pick_count=len(scores))
            return scores

    def run_match(*, sport, home_team, away_team, event_date, markets):
        if sport == "nfl":
            from nfl_collection import NflCollector
            from nfl_domain import NFL_PLAYER_MARKETS, NFL_GAME_MARKETS
            from nfl_module import NflModule
            nfl_module = NflModule(collector=NflCollector(discovery_client.client, timezone_name=request_dict.get("timezone")))
            group = request_dict.get("nfl_market_group", "all")
            markets = NFL_PLAYER_MARKETS if group == "player_props" else NFL_GAME_MARKETS if group == "game_bets" else markets
            match_inputs = nfl_module.collect_inputs(
                home_team=home_team, away_team=away_team, match_date=event_date, markets=markets
            )
            module = nfl_module
        else:
            module = get_sport_module(sport)
            match_inputs = module.collect_inputs(
                home_team=home_team, away_team=away_team, match_date=event_date
            )
        scores = module.score(match_inputs, markets=markets)
        if sport == "nfl" and not scores:
            from nfl_module import NflNoPicks
            raise NflNoPicks((match_inputs.get("recommendation_summary") or {}).get("message") or "No verified NFL picks qualified.")
        return scores

    def get_token_usage() -> tuple[int, int, int]:
        llm = getattr(discovery_client, "_client", None)
        cumulative = getattr(llm, "cumulative_token_usage", None)
        if cumulative:
            return (cumulative.prompt_tokens, cumulative.completion_tokens, cumulative.total_tokens)
        return (0, 0, 0)

    catalog_read_fn = None
    try:
        from services.catalog.read_service import CatalogFirstReader
        from services.catalog.rollout import CatalogReadMode, resolve_read_mode
        from services.catalog.storage import CatalogStore

        read_mode = resolve_read_mode(os.getenv("COLMILLO_CATALOG_READ_MODE", "shadow"))
        if read_mode != CatalogReadMode.LIVE:
            db_path = os.getenv("COLMILLO_CATALOG_DB_PATH", "data/catalog.db")
            catalog_store = CatalogStore(db_path)
            reader = CatalogFirstReader(
                lookup=lambda s, h, a, d: catalog_store.find_snapshot(sport=s, home_team=h, away_team=a, event_date=d),
            )
            catalog_read_fn = reader.read
    except Exception:
        catalog_read_fn = None

    return SlateOrchestrationDeps(
        discover_matches=discover,
        run_match_pipeline=run_pipeline,
        get_token_usage=get_token_usage,
        read_catalog=catalog_read_fn,
    )


def _slate_row_to_detail(row: Any) -> SlateDetailResponse:
    request = json.loads(row.request_json) if row.request_json else {}
    candidates = json.loads(row.candidates_json) if row.candidates_json else []
    match_runs = json.loads(row.match_runs_json) if row.match_runs_json else []
    return SlateDetailResponse(
        operation_id=getattr(row, "operation_id", None),
        outcome=getattr(row, "outcome", None),
        id=row.id,
        created_at=row.created_at,
        status=row.status,
        request=request,
        candidates=[SlateRankedCandidate(**c) for c in candidates],
        match_runs=[SlateMatchRunSummary(**m) for m in match_runs],
        matches_attempted=row.matches_attempted,
        matches_succeeded=row.matches_succeeded,
        latency_ms=row.latency_ms,
        discovery_latency_ms=row.discovery_latency_ms,
        prompt_tokens=getattr(row, "prompt_tokens", None),
        completion_tokens=getattr(row, "completion_tokens", None),
        total_tokens=getattr(row, "total_tokens", None),
        error_stage=row.error_stage,
        error_message=row.error_message,
        progress_stage=getattr(row, "progress_stage", None),
        matches_discovered=getattr(row, "matches_discovered", None),
        matches_completed=getattr(row, "matches_completed", None),
        heartbeat_at=getattr(row, "heartbeat_at", None),
        stop_reason=getattr(row, "stop_reason", None),
        resume_count=getattr(row, "resume_count", 0) or 0,
    )


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
    catalog_store = CatalogStore(os.getenv("COLMILLO_CATALOG_DB", str(_REPO_ROOT / "data" / "catalog.db")))

    @app.get("/catalog/events")
    def catalog_events(
        sport: str | None = Query(None),
        start_from: str | None = Query(None),
        start_to: str | None = Query(None),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        return {"items": catalog_store.list_events(sport=sport, start_from=start_from,
                                                     start_to=start_to, limit=limit, offset=offset),
                "limit": limit, "offset": offset, "catalog": catalog_store.health()}

    @app.get("/catalog/health")
    def catalog_health() -> dict[str, Any]:
        return catalog_store.health(operational=True)

    @app.get("/catalog/settings")
    def catalog_settings() -> dict[str, Any]:
        return {"items": catalog_store.list_sport_settings()}

    @app.put("/catalog/settings/{sport}")
    def update_catalog_settings(
        sport: str, payload: CatalogSportSettingsRequest
    ) -> dict[str, Any]:
        try:
            return catalog_store.set_sport_enabled(sport, enabled=payload.enabled)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/catalog/refresh", status_code=202)
    def refresh_catalog(
        payload: CatalogRefreshRequest, background_tasks: BackgroundTasks
    ) -> dict[str, str]:
        try:
            datetime.strptime(payload.date, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="date must be a valid YYYY-MM-DD value."
            ) from exc
        job_id = start_fanatics_refresh(catalog_store, run_date=payload.date)
        if job_id is None:
            raise HTTPException(status_code=409, detail="A catalog refresh is already running.")
        background_tasks.add_task(
            run_fanatics_refresh, catalog_store, job_id=job_id, run_date=payload.date
        )
        return {"job_id": job_id}

    @app.get("/catalog/jobs/{job_id}")
    def catalog_job(job_id: str) -> dict[str, Any]:
        job = catalog_store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Catalog refresh job not found.")
        summary = job.get("summary")
        if isinstance(summary, str):
            try:
                job["summary"] = json.loads(summary)
            except json.JSONDecodeError:
                pass
        return job

    @app.get("/catalog/events/{event_id}/snapshot")
    def catalog_snapshot(event_id: str) -> dict[str, Any]:
        snapshot = catalog_store.get_latest_snapshot(event_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Catalog snapshot not found.")
        return snapshot

    @app.get("/catalog/archive/{archive_id}")
    def catalog_archive(archive_id: str) -> dict[str, Any]:
        archive = catalog_store.get_raw_archive(archive_id)
        if archive is None:
            raise HTTPException(status_code=404, detail="Catalog archive not found.")
        return archive

    @app.post("/enrichment/audit", response_model=EnrichmentAuditResponse)
    def enrichment_audit(payload: EnrichmentAuditRequest) -> EnrichmentAuditResponse:
        return execute_enrichment_audit(payload)

    from services.api.diagnostics_routes import admin_router, router as diagnostics_router
    app.include_router(diagnostics_router)
    app.include_router(admin_router)

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
    @instrument("discovery")
    def discover_matches(payload: MatchDiscoveryRequest) -> MatchDiscoveryResponse:
        import time as _time
        from datetime import datetime, timedelta, timezone as _dt_tz

        from match_discovery import (
            MatchDiscoveryError,
            MatchDiscoveryValidationError,
            validate_match_discovery_inputs,
        )

        logger.info(
            "match_discovery_started",
            extra={"date": payload.date, "sports": payload.sports, "limit_per_sport": payload.limit_per_sport},
        )
        t0 = _time.perf_counter()

        try:
            sports = validate_match_discovery_inputs(
                date_utc=payload.date,
                sports=payload.sports,
                limit_per_sport=payload.limit_per_sport,
            )
        except MatchDiscoveryValidationError as exc:
            latency_ms = int((_time.perf_counter() - t0) * 1000)
            logger.warning(
                "match_discovery_failed",
                extra={"error": "; ".join(exc.errors), "latency_ms": latency_ms},
            )
            raise HTTPException(status_code=400, detail="; ".join(exc.errors)) from exc

        cache_key = _discovery_cache_key(
            date=payload.date, sports=sports, limit=payload.limit_per_sport,
            timezone_name=payload.timezone, provider=payload.llm_provider, model=payload.llm_model,
        )
        now_iso = datetime.now(_dt_tz.utc).isoformat()
        if not payload.force_refresh:
            cached = catalog_store.get_discovery_cache(cache_key, now=now_iso)
            if cached is not None:
                return MatchDiscoveryResponse(**cached)

        try:
            client = _build_match_discovery_client(payload)
            result = client.discover_matches(
                date_utc=payload.date,
                sports=sports,
                limit_per_sport=payload.limit_per_sport,
                timezone=payload.timezone,
            )
        except MatchDiscoveryError as exc:
            latency_ms = int((_time.perf_counter() - t0) * 1000)
            logger.warning(
                "match_discovery_failed",
                extra={"error": str(exc), "latency_ms": latency_ms},
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        latency_ms = int((_time.perf_counter() - t0) * 1000)
        total_matches = sum(
            len(sport_result.get("matches", []))
            for sport_result in result.get("results", {}).values()
        )
        failures = sum(bool(v.get("error")) for v in result.get("results", {}).values())
        unavailable = sum(
            isinstance(v, dict) and (v.get("data_quality") or {}).get("status") == "unavailable"
            for v in result.get("results", {}).values()
        )
        finish_operation("partial" if failures and total_matches else "failed" if failures else "success" if total_matches else "no_picks",
                         count=total_matches, failed_count=failures)
        logger.info(
            "match_discovery_completed",
            extra={
                "date": payload.date,
                "sports": payload.sports,
                "total_matches": total_matches,
                "latency_ms": latency_ms,
            },
        )

        result_copy = dict(result)
        # A provider error is a transient observation, never a four-hour success.
        # Return healthy sports immediately, but allow the next request to recover the
        # failed sport rather than replaying an error from cache.
        if failures or unavailable:
            result_copy["cache_status"] = "uncached"
            result_copy["cache_confidence"] = "partial"
            result_copy["cache_expires_at"] = None
            return MatchDiscoveryResponse(**result_copy)

        cache_ttl = timedelta(hours=4) if total_matches else timedelta(minutes=15)
        confidence = "high" if total_matches else "medium"
        expires_iso = (datetime.now(_dt_tz.utc) + cache_ttl).isoformat()
        catalog_store.save_discovery_cache(
            cache_key=cache_key,
            response=result,
            confidence=confidence,
            created_at=now_iso,
            expires_at=expires_iso,
        )
        result_copy["cache_status"] = "refreshed"
        result_copy["cache_confidence"] = confidence
        result_copy["cache_expires_at"] = expires_iso
        return MatchDiscoveryResponse(**result_copy)

    @app.delete("/matches/discover/cache")
    def clear_match_discovery_cache(payload: MatchDiscoveryRequest) -> dict[str, bool]:
        from match_discovery import validate_match_discovery_inputs
        sports = validate_match_discovery_inputs(date_utc=payload.date, sports=payload.sports, limit_per_sport=payload.limit_per_sport)
        key = _discovery_cache_key(
            date=payload.date, sports=sports, limit=payload.limit_per_sport,
            timezone_name=payload.timezone, provider=payload.llm_provider, model=payload.llm_model,
        )
        discarded = catalog_store.clear_discovery_cache(key)
        return {"discarded": discarded}

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
        if row.error_details_json:
            try:
                error_details = json.loads(row.error_details_json)
            except Exception:
                error_details = None
        safe_error_details = public_trace(error_details)
        return PickStatusResponse(
            operation_id=getattr(row, "operation_id", None),
            outcome=getattr(row, "outcome", None),
            id=row.id,
            status=row.status,
            error_stage=row.error_stage,
            error_message=row.error_message,
            latency_ms=row.latency_ms,
            error_details=safe_error_details if isinstance(safe_error_details, dict) else None,
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

    # ---- Batch Availability (slate candidates) ----------------------------- #
    @app.post(
        "/availability/check-batch",
        response_model=BatchAvailabilityResponse,
    )
    def check_availability_batch(payload: BatchAvailabilityRequest) -> BatchAvailabilityResponse:
        try:
            badges = _check_availability_for_picks(payload.candidates, payload.platforms)
        except Exception as exc:
            return BatchAvailabilityResponse(
                badges=[],
                fallback_mode=True,
                fallback_reason=f"Adapter error: {exc}",
                checked_at=datetime.now(timezone.utc).isoformat(),
            )

        return BatchAvailabilityResponse(
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
                    operation_id=getattr(r, "operation_id", None),
                    outcome=getattr(r, "outcome", None),
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
            operation_id=getattr(run, "operation_id", None) or run.request_snapshot.get("operation_id"),
            outcome=getattr(run, "outcome", None),
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
                    source_pick=p.source_pick,
                )
                for p in picks
            ],
        )

    # ---- Slates (async) -------------------------------------------------- #

    _SUPPORTED_SLATE_SPORTS = {"soccer", "basketball", "baseball", "nfl"}

    @app.get("/slates", response_model=SlateListResponse)
    def list_slates(
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> SlateListResponse:
        rows = db_module.list_slate_runs(limit=limit, offset=offset)
        items = [
            SlateSummary(
                operation_id=getattr(row, "operation_id", None),
                outcome=getattr(row, "outcome", None),
                id=row.id,
                created_at=row.created_at,
                status=row.status,
                request=json.loads(row.request_json) if row.request_json else {},
                latency_ms=row.latency_ms,
                progress_stage=getattr(row, "progress_stage", None),
                matches_discovered=getattr(row, "matches_discovered", None),
                matches_completed=getattr(row, "matches_completed", None),
                heartbeat_at=getattr(row, "heartbeat_at", None),
                stop_reason=getattr(row, "stop_reason", None),
            )
            for row in rows
        ]
        return SlateListResponse(items=items, limit=limit, offset=offset)

    @app.post("/slates", response_model=SlateAcceptedResponse, status_code=202)
    def create_slate(payload: SlateRequest, background_tasks: BackgroundTasks) -> SlateAcceptedResponse:
        try:
            datetime.strptime(payload.date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid date '{payload.date}'. Expected YYYY-MM-DD.")

        unsupported = set(s.lower() for s in payload.sports) - _SUPPORTED_SLATE_SPORTS
        if unsupported:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported sport(s): {sorted(unsupported)}. Supported: {sorted(_SUPPORTED_SLATE_SPORTS)}",
            )

        request_dict = payload.model_dump()
        row = db_module.create_pending_slate_run(request_payload=request_dict)
        jobs_module.enqueue_slate_run(row.id, request_dict)

        worker_mode = os.getenv("COLMILLO_WORKER_MODE", "").lower()
        if worker_mode != "external":
            background_tasks.add_task(_run_next_queued_slate_job)

        return SlateAcceptedResponse(id=row.id, status=row.status, created_at=row.created_at, operation_id=row.operation_id)

    @app.get("/slates/{slate_id}", response_model=SlateDetailResponse)
    def get_slate(slate_id: str) -> SlateDetailResponse:
        row = db_module.get_slate_run(slate_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Slate not found.")
        return _slate_row_to_detail(row)

    @app.get("/slates/{slate_id}/status", response_model=SlateStatusResponse)
    def get_slate_status(slate_id: str) -> SlateStatusResponse:
        row = db_module.get_slate_run(slate_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Slate not found.")
        return SlateStatusResponse(
            operation_id=getattr(row, "operation_id", None),
            outcome=getattr(row, "outcome", None),
            id=row.id,
            status=row.status,
            error_stage=row.error_stage,
            error_message=row.error_message,
            latency_ms=row.latency_ms,
            progress_stage=getattr(row, "progress_stage", None),
            matches_discovered=getattr(row, "matches_discovered", None),
            matches_completed=getattr(row, "matches_completed", None),
            heartbeat_at=getattr(row, "heartbeat_at", None),
            stop_reason=getattr(row, "stop_reason", None),
            resume_count=getattr(row, "resume_count", 0) or 0,
        )

    @app.post("/slates/{slate_id}/resume", response_model=SlateAcceptedResponse, status_code=202)
    def resume_slate(slate_id: str, background_tasks: BackgroundTasks) -> SlateAcceptedResponse:
        request_dict = db_module.prepare_slate_resume(slate_id=slate_id)
        if request_dict is None:
            raise HTTPException(status_code=409, detail="Only interrupted slates can be resumed.")
        row = db_module.get_slate_run(slate_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Slate not found.")
        jobs_module.enqueue_slate_run(slate_id=slate_id, request_dict=request_dict)
        if os.getenv("COLMILLO_WORKER_MODE", "").lower() != "external":
            background_tasks.add_task(_run_next_queued_slate_job)
        return SlateAcceptedResponse(id=row.id, status="queued", created_at=row.created_at, operation_id=row.operation_id)

    return app


app = create_app()
