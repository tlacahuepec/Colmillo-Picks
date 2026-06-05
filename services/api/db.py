"""SQLAlchemy model + session helpers for the picks history table.

We use a small custom layer (rather than reaching for Alembic) because the MVP
only has one table and runs on SQLite. ``init_db()`` runs ``create_all`` at app
startup, which is acceptable for additive schemas on SQLite.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


# Job status constants used by the async pick pipeline.
PICK_STATUS_PENDING = "pending"
PICK_STATUS_QUEUED = "queued"
PICK_STATUS_RUNNING = "running"
PICK_STATUS_SUCCESS = "success"
PICK_STATUS_FAILED = "failed"


class PickRun(Base):
    """One row per ``POST /picks`` invocation.

    Created in ``pending`` state when the request is accepted. The background
    worker updates the row to ``success`` (and fills the payload) or ``failed``
    (with ``error_stage`` / ``error_message``).
    """

    __tablename__ = "picks_history"

    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    match_query = Column(String(255), nullable=False)
    competition = Column(String(255), nullable=True)
    top_n = Column(Integer, nullable=False)
    request_json = Column(Text, nullable=False)
    report_markdown = Column(Text, nullable=False, default="")
    scores_json = Column(Text, nullable=False, default="[]")
    trace_json = Column(Text, nullable=True)
    fixture_status = Column(String(64), nullable=True)
    llm_status = Column(String(64), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, default=PICK_STATUS_PENDING)
    error_stage = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    error_details_json = Column(Text, nullable=True)  # Rich observability context for failures (Epic #219)
    sport = Column(String(32), nullable=True)
    league = Column(String(64), nullable=True)
    markets_json = Column(Text, nullable=True)
    scheduled_kickoff_utc = Column(DateTime(timezone=True), nullable=True)


class PickOutcome(Base):
    """User-recorded outcome for an individual pick.

    Stored separately from ``picks_history`` so we can append outcomes after
    the match settles without touching the original payload.
    """

    __tablename__ = "pick_outcomes"

    id = Column(String(36), primary_key=True)
    pick_id = Column(String(36), nullable=False, index=True)
    rank = Column(Integer, nullable=False)
    player = Column(String(255), nullable=False)
    market = Column(String(64), nullable=False)
    result = Column(String(8), nullable=False)  # win | loss | push | void
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    resolution_attempted_at = Column(DateTime(timezone=True), nullable=True)
    last_resolution_error = Column(Text, nullable=True)


class PickJob(Base):
    """Queue row associated with one pick run."""

    __tablename__ = "pick_jobs"

    id = Column(String(36), primary_key=True)
    pick_id = Column(String(36), nullable=False, index=True)
    request_json = Column(Text, nullable=False)
    bundle_kwargs_json = Column(Text, nullable=False)
    state = Column(String(16), nullable=False, default=PICK_STATUS_QUEUED)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class SlateRun(Base):
    """One row per ``POST /slates`` invocation."""

    __tablename__ = "slate_runs"

    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(16), nullable=False, default=PICK_STATUS_PENDING)
    request_json = Column(Text, nullable=False)
    candidates_json = Column(Text, nullable=False, default="[]")
    match_runs_json = Column(Text, nullable=False, default="[]")
    latency_ms = Column(Integer, nullable=True)
    discovery_latency_ms = Column(Integer, nullable=True)
    error_stage = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    matches_attempted = Column(Integer, nullable=True)
    matches_succeeded = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)


class SlateJob(Base):
    """Queue row associated with one slate run."""

    __tablename__ = "slate_jobs"

    id = Column(String(36), primary_key=True)
    slate_id = Column(String(36), nullable=False, index=True)
    request_json = Column(Text, nullable=False)
    state = Column(String(16), nullable=False, default=PICK_STATUS_QUEUED)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


# Module-level engine/session factory; rebuilt by ``configure_engine`` so tests
# can swap in an in-memory database without restarting the app.
_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _default_db_url() -> str:
    raw = os.getenv("COLMILLO_DB_PATH", "").strip()
    if not raw:
        raw = "./data/colmillo.db"
    db_path = Path(raw).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def _ensure_added_columns(engine: Engine) -> None:
    """Lightweight forward migration for additive columns on SQLite.

    ``Base.metadata.create_all`` only creates tables that don't yet exist; it
    won't add columns to a pre-existing table. For each known additive column
    we issue ``ALTER TABLE ... ADD COLUMN`` when it's missing so existing
    deployments pick up new fields without manual SQL.
    """
    inspector = inspect(engine)
    if "picks_history" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("picks_history")}
        additive: list[tuple[str, str]] = [
            ("status", f"VARCHAR(16) NOT NULL DEFAULT '{PICK_STATUS_PENDING}'"),
            ("error_stage", "VARCHAR(64)"),
            ("error_message", "TEXT"),
            ("error_details_json", "TEXT"),  # Rich observability context for failures (Epic #219)
            ("sport", "VARCHAR(32)"),
            ("league", "VARCHAR(64)"),
            ("markets_json", "TEXT"),
            ("scheduled_kickoff_utc", "TIMESTAMP"),
        ]
        with engine.begin() as conn:
            for col_name, col_def in additive:
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE picks_history ADD COLUMN {col_name} {col_def}"))

    if "pick_outcomes" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("pick_outcomes")}
        outcome_additive: list[tuple[str, str]] = [
            ("resolution_attempted_at", "TIMESTAMP"),
            ("last_resolution_error", "TEXT"),
        ]
        with engine.begin() as conn:
            for col_name, col_def in outcome_additive:
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE pick_outcomes ADD COLUMN {col_name} {col_def}"))


def configure_engine(url: str | None = None) -> Engine:
    """(Re-)build the global engine + session factory and create tables."""
    global _engine, _SessionFactory
    db_url = url or _default_db_url()
    # ``check_same_thread=False`` is required when SQLite is shared across the
    # FastAPI thread pool used by sync route handlers.
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    _engine = create_engine(db_url, future=True, connect_args=connect_args)
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    Base.metadata.create_all(_engine)
    _ensure_added_columns(_engine)
    return _engine


def init_db() -> Engine:
    """Idempotent initializer used at application startup."""
    if _engine is None:
        configure_engine()
    return _engine  # type: ignore[return-value]


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session that commits on success and rolls back on error."""
    if _SessionFactory is None:
        init_db()
    assert _SessionFactory is not None
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# CRUD helpers used by the API handlers                                       #
# --------------------------------------------------------------------------- #


def _safe_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip secrets / auth headers before persisting the request body.

    The pick request schema does not currently carry secrets, but we filter
    explicitly anyway so future fields don't accidentally land in the DB.
    """
    sensitive_keys = {"x_api_key", "authorization", "api_key"}
    return {k: v for k, v in payload.items() if k.lower() not in sensitive_keys}


def _normalize_status_value(value: Any, *, max_len: int = 64) -> str | None:
    """Convert provider/status payloads to a compact DB-safe string.

    Some providers return structured status objects (for example
    ``{"short": "NS", "long": "Not Started"}``) while DB columns are
    ``VARCHAR``. Normalize to a short scalar to avoid sqlite bind errors.
    """
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized[:max_len] if normalized else None
    if isinstance(value, dict):
        for key in ("short", "status", "state", "code", "long", "label", "name"):
            candidate = value.get(key)
            if candidate is None:
                continue
            normalized = _normalize_status_value(candidate, max_len=max_len)
            if normalized:
                return normalized
        for candidate in value.values():
            normalized = _normalize_status_value(candidate, max_len=max_len)
            if normalized:
                return normalized
        return None
    normalized = str(value).strip()
    return normalized[:max_len] if normalized else None


def create_pending_pick_run(*, request_payload: dict[str, Any]) -> PickRun:
    """Insert a ``pending`` row for an accepted async pick request."""
    competition_value = request_payload.get("league") or request_payload.get("competition")
    competition_text = str(competition_value)[:255] if competition_value else None
    row = PickRun(
        id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        match_query=str(request_payload.get("match_query", ""))[:255],
        competition=competition_text,
        top_n=int(request_payload.get("top_n", 5)),
        request_json=json.dumps(_safe_request_payload(request_payload), default=str),
        report_markdown="",
        scores_json="[]",
        trace_json=None,
        fixture_status=None,
        llm_status=None,
        latency_ms=None,
        status=PICK_STATUS_PENDING,
        sport=str(request_payload.get("sport", "soccer"))[:32] if request_payload.get("sport") else None,
        league=str(request_payload.get("league", ""))[:64] or None,
        markets_json=json.dumps(request_payload.get("markets")) if request_payload.get("markets") else None,
    )
    with session_scope() as session:
        session.add(row)
    return row


def enqueue_pick_job(*, pick_id: str, request_dict: dict[str, Any], bundle_kwargs: dict[str, Any]) -> PickJob:
    now = datetime.now(timezone.utc)
    job = PickJob(
        id=str(uuid.uuid4()),
        pick_id=pick_id,
        request_json=json.dumps(request_dict, default=str),
        bundle_kwargs_json=json.dumps(bundle_kwargs, default=str),
        state=PICK_STATUS_QUEUED,
        attempts=0,
        last_error=None,
        created_at=now,
        updated_at=now,
    )
    with session_scope() as session:
        row = session.get(PickRun, pick_id)
        if row is not None:
            row.status = PICK_STATUS_QUEUED
            session.add(row)
        session.add(job)
    return job


def dequeue_pick_job() -> PickJob | None:
    with session_scope() as session:
        now = datetime.now(timezone.utc)
        claimed = session.execute(
            text(
                """
                UPDATE pick_jobs
                SET state = :running_state,
                    attempts = attempts + 1,
                    updated_at = :updated_at
                WHERE id = (
                    SELECT id
                    FROM pick_jobs
                    WHERE state = :queued_state
                    ORDER BY created_at ASC
                    LIMIT 1
                )
                RETURNING id
                """
            ),
            {
                "running_state": PICK_STATUS_RUNNING,
                "queued_state": PICK_STATUS_QUEUED,
                "updated_at": now,
            },
        ).first()
        if claimed is None:
            return None

        job = session.get(PickJob, str(claimed.id))
        if job is None:
            return None

        row = session.get(PickRun, job.pick_id)
        if row is not None:
            row.status = PICK_STATUS_RUNNING
            session.add(row)
        session.add(job)
        session.flush()
        session.refresh(job)
        return job


def mark_job_finished(*, job_id: str, success: bool, error_message: str | None = None) -> None:
    with session_scope() as session:
        job = session.get(PickJob, job_id)
        if job is None:
            return
        job.state = PICK_STATUS_SUCCESS if success else PICK_STATUS_FAILED
        job.last_error = error_message
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)


def mark_pick_success(
    *,
    pick_id: str,
    result: dict[str, Any],
    latency_ms: int,
) -> PickRun | None:
    """Update a pending row with the rendered pipeline output."""
    trace = result.get("trace") or {}
    match_inputs = result.get("match_inputs") or {}
    fixture_status = None
    match_meta = match_inputs.get("match") if isinstance(match_inputs, dict) else None
    if isinstance(match_meta, dict):
        fixture_status = _normalize_status_value(
            match_meta.get("fixture_status") or match_meta.get("status")
        )

    with session_scope() as session:
        row = session.get(PickRun, pick_id)
        if row is None:
            return None
        row.status = PICK_STATUS_SUCCESS
        row.report_markdown = str(result.get("report_markdown", ""))
        row.scores_json = json.dumps(result.get("scores", []), default=str)
        row.trace_json = json.dumps(trace, default=str) if trace else None
        row.fixture_status = fixture_status
        row.llm_status = (
            _normalize_status_value(trace.get("llm_status")) if isinstance(trace, dict) else None
        )
        row.latency_ms = latency_ms
        row.error_stage = None
        row.error_message = None
        session.add(row)
        session.flush()
        session.refresh(row)
        return row


def mark_pick_failed(
    *,
    pick_id: str,
    stage: str,
    message: str,
    latency_ms: int,
    error_details: dict[str, Any] | None = None,
) -> PickRun | None:
    """Update a pending row with failure metadata.
    error_details carries rich observability context (provider_status, critical_missing_fields, etc.)
    for Epic #219 cross-sport failure surfacing.
    """
    import json
    with session_scope() as session:
        row = session.get(PickRun, pick_id)
        if row is None:
            return None
        row.status = PICK_STATUS_FAILED
        row.error_stage = stage[:64]
        row.error_message = message
        if error_details:
            row.error_details_json = json.dumps(error_details, default=str)
        row.latency_ms = latency_ms
        session.add(row)
        session.flush()
        session.refresh(row)
        return row


def list_pick_runs(*, limit: int, offset: int, sport: str | None = None) -> list[PickRun]:
    with session_scope() as session:
        query = session.query(PickRun).order_by(PickRun.created_at.desc())
        if sport is not None:
            query = query.filter(PickRun.sport == sport)
        return list(query.limit(limit).offset(offset).all())


def get_pick_run(pick_id: str) -> PickRun | None:
    with session_scope() as session:
        return session.get(PickRun, pick_id)


# --------------------------------------------------------------------------- #
# Outcomes (Story 9)                                                          #
# --------------------------------------------------------------------------- #


VALID_OUTCOME_RESULTS = frozenset({"win", "loss", "push", "void"})


def record_outcomes(*, pick_id: str, outcomes: list[dict[str, Any]]) -> list[PickOutcome]:
    """Persist a batch of per-pick outcomes; returns the inserted rows."""
    now = datetime.now(timezone.utc)
    rows: list[PickOutcome] = []
    for entry in outcomes:
        result_value = str(entry.get("result", "")).lower()
        if result_value not in VALID_OUTCOME_RESULTS:
            raise ValueError(
                f"Invalid outcome result '{result_value}'. "
                f"Allowed: {sorted(VALID_OUTCOME_RESULTS)}."
            )
        rows.append(
            PickOutcome(
                id=str(uuid.uuid4()),
                pick_id=pick_id,
                rank=int(entry.get("rank", 0)),
                player=str(entry.get("player", ""))[:255],
                market=str(entry.get("market", ""))[:64],
                result=result_value,
                recorded_at=now,
            )
        )
    with session_scope() as session:
        session.add_all(rows)
    return rows


def list_outcomes(pick_id: str) -> list[PickOutcome]:
    with session_scope() as session:
        return list(
            session.query(PickOutcome)
            .filter(PickOutcome.pick_id == pick_id)
            .order_by(PickOutcome.rank.asc(), PickOutcome.recorded_at.asc())
            .all()
        )


def hit_rate_summary(*, since: datetime | None = None) -> dict[str, Any]:
    """Aggregate outcomes into counts and a hit rate.

    A "hit" is any ``win`` outcome. ``push`` and ``void`` are excluded from
    both numerator and denominator. ``loss`` counts toward the denominator.
    """
    with session_scope() as session:
        query = session.query(PickOutcome)
        if since is not None:
            query = query.filter(PickOutcome.recorded_at >= since)
        outcomes = query.all()
    totals: dict[str, int] = {key: 0 for key in VALID_OUTCOME_RESULTS}
    for outcome in outcomes:
        totals[outcome.result] = totals.get(outcome.result, 0) + 1
    decided = totals.get("win", 0) + totals.get("loss", 0)
    hit_rate = (totals.get("win", 0) / decided) if decided else None
    return {
        "totals": totals,
        "decided": decided,
        "hit_rate": hit_rate,
        "since": since.isoformat() if since else None,
    }


# --------------------------------------------------------------------------- #
# Operational stats (Story 10)                                                #
# --------------------------------------------------------------------------- #


def operational_stats() -> dict[str, Any]:
    """Aggregate pipeline run stats for ``/admin/stats``."""
    from sqlalchemy import func

    with session_scope() as session:
        total = session.query(func.count(PickRun.id)).scalar() or 0
        by_status: dict[str, int] = {}
        for status_value, count in session.query(PickRun.status, func.count(PickRun.id)).group_by(PickRun.status).all():
            by_status[str(status_value)] = int(count)
        avg_latency = session.query(func.avg(PickRun.latency_ms)).filter(
            PickRun.status == PICK_STATUS_SUCCESS
        ).scalar()
        last_failed = (
            session.query(PickRun)
            .filter(PickRun.status == PICK_STATUS_FAILED)
            .order_by(PickRun.created_at.desc())
            .limit(5)
            .all()
        )
        recent_failures = [
            {
                "id": row.id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "stage": row.error_stage,
                "message": row.error_message,
            }
            for row in last_failed
        ]
        outcomes_count = session.query(func.count(PickOutcome.id)).scalar() or 0
    return {
        "total_runs": int(total),
        "by_status": by_status,
        "avg_success_latency_ms": float(avg_latency) if avg_latency is not None else None,
        "recent_failures": recent_failures,
        "outcomes_recorded": int(outcomes_count),
    }


# --------------------------------------------------------------------------- #
# Outcome resolution queries (Issue #74)                                       #
# --------------------------------------------------------------------------- #


def list_unresolved_picks(*, settled_before: datetime) -> list[PickRun]:
    """Return successful picks past kickoff that have no recorded outcomes yet.

    A pick is "unresolved" when:
    - status == success
    - scheduled_kickoff_utc is set and < settled_before
    - no PickOutcome rows exist for that pick_id
    """
    from sqlalchemy import exists

    with session_scope() as session:
        outcome_exists = exists().where(PickOutcome.pick_id == PickRun.id)
        return list(
            session.query(PickRun)
            .filter(
                PickRun.status == PICK_STATUS_SUCCESS,
                PickRun.scheduled_kickoff_utc.isnot(None),
                PickRun.scheduled_kickoff_utc < settled_before,
                ~outcome_exists,
            )
            .order_by(PickRun.scheduled_kickoff_utc.asc())
            .all()
        )


# --------------------------------------------------------------------------- #
# Slate CRUD helpers (Issue #212)                                              #
# --------------------------------------------------------------------------- #


def create_pending_slate_run(*, request_payload: dict[str, Any]) -> SlateRun:
    row = SlateRun(
        id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        status=PICK_STATUS_PENDING,
        request_json=json.dumps(_safe_request_payload(request_payload), default=str),
        candidates_json="[]",
        match_runs_json="[]",
    )
    with session_scope() as session:
        session.add(row)
    return row


def enqueue_slate_job(*, slate_id: str, request_dict: dict[str, Any]) -> SlateJob:
    now = datetime.now(timezone.utc)
    job = SlateJob(
        id=str(uuid.uuid4()),
        slate_id=slate_id,
        request_json=json.dumps(request_dict, default=str),
        state=PICK_STATUS_QUEUED,
        attempts=0,
        last_error=None,
        created_at=now,
        updated_at=now,
    )
    with session_scope() as session:
        row = session.get(SlateRun, slate_id)
        if row is not None:
            row.status = PICK_STATUS_QUEUED
            session.add(row)
        session.add(job)
    return job


def dequeue_slate_job() -> SlateJob | None:
    with session_scope() as session:
        now = datetime.now(timezone.utc)
        claimed = session.execute(
            text(
                """
                UPDATE slate_jobs
                SET state = :running_state,
                    attempts = attempts + 1,
                    updated_at = :updated_at
                WHERE id = (
                    SELECT id
                    FROM slate_jobs
                    WHERE state = :queued_state
                    ORDER BY created_at ASC
                    LIMIT 1
                )
                RETURNING id
                """
            ),
            {
                "running_state": PICK_STATUS_RUNNING,
                "queued_state": PICK_STATUS_QUEUED,
                "updated_at": now,
            },
        ).first()
        if claimed is None:
            return None

        job = session.get(SlateJob, str(claimed.id))
        if job is None:
            return None

        row = session.get(SlateRun, job.slate_id)
        if row is not None:
            row.status = PICK_STATUS_RUNNING
            session.add(row)
        session.add(job)
        session.flush()
        session.refresh(job)
        return job


def mark_slate_success(
    *,
    slate_id: str,
    candidates: list[dict[str, Any]],
    match_runs: list[dict[str, Any]],
    latency_ms: int,
    discovery_latency_ms: int,
    matches_attempted: int,
    matches_succeeded: int,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
) -> SlateRun | None:
    with session_scope() as session:
        row = session.get(SlateRun, slate_id)
        if row is None:
            return None
        row.status = PICK_STATUS_SUCCESS
        row.candidates_json = json.dumps(candidates, default=str)
        row.match_runs_json = json.dumps(match_runs, default=str)
        row.latency_ms = latency_ms
        row.discovery_latency_ms = discovery_latency_ms
        row.matches_attempted = matches_attempted
        row.matches_succeeded = matches_succeeded
        row.prompt_tokens = prompt_tokens
        row.completion_tokens = completion_tokens
        row.total_tokens = total_tokens
        row.error_stage = None
        row.error_message = None
        session.add(row)
        session.flush()
        session.refresh(row)
        return row


def mark_slate_failed(
    *,
    slate_id: str,
    stage: str,
    message: str,
    latency_ms: int,
) -> SlateRun | None:
    with session_scope() as session:
        row = session.get(SlateRun, slate_id)
        if row is None:
            return None
        row.status = PICK_STATUS_FAILED
        row.error_stage = stage[:64]
        row.error_message = message
        row.latency_ms = latency_ms
        session.add(row)
        session.flush()
        session.refresh(row)
        return row


def mark_slate_job_finished(*, job_id: str, success: bool, error_message: str | None = None) -> None:
    with session_scope() as session:
        job = session.get(SlateJob, job_id)
        if job is None:
            return
        job.state = PICK_STATUS_SUCCESS if success else PICK_STATUS_FAILED
        job.last_error = error_message
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)


def get_slate_run(slate_id: str) -> SlateRun | None:
    with session_scope() as session:
        return session.get(SlateRun, slate_id)


def list_slate_runs(*, limit: int, offset: int) -> list[SlateRun]:
    with session_scope() as session:
        return list(
            session.query(SlateRun)
            .order_by(SlateRun.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
