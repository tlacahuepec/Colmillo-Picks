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
    if "picks_history" not in inspector.get_table_names():
        return
    existing_cols = {col["name"] for col in inspector.get_columns("picks_history")}
    additive: list[tuple[str, str]] = [
        ("status", f"VARCHAR(16) NOT NULL DEFAULT '{PICK_STATUS_PENDING}'"),
        ("error_stage", "VARCHAR(64)"),
        ("error_message", "TEXT"),
    ]
    with engine.begin() as conn:
        for col_name, col_def in additive:
            if col_name not in existing_cols:
                conn.execute(text(f"ALTER TABLE picks_history ADD COLUMN {col_name} {col_def}"))


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
    )
    with session_scope() as session:
        session.add(row)
    return row


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
        fixture_status = match_meta.get("fixture_status") or match_meta.get("status")

    with session_scope() as session:
        row = session.get(PickRun, pick_id)
        if row is None:
            return None
        row.status = PICK_STATUS_SUCCESS
        row.report_markdown = str(result.get("report_markdown", ""))
        row.scores_json = json.dumps(result.get("scores", []), default=str)
        row.trace_json = json.dumps(trace, default=str) if trace else None
        row.fixture_status = fixture_status
        row.llm_status = trace.get("llm_status") if isinstance(trace, dict) else None
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
) -> PickRun | None:
    """Update a pending row with failure metadata."""
    with session_scope() as session:
        row = session.get(PickRun, pick_id)
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


def list_pick_runs(*, limit: int, offset: int) -> list[PickRun]:
    with session_scope() as session:
        return list(
            session.query(PickRun)
            .order_by(PickRun.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )


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
