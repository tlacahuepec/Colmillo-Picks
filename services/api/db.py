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

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class PickRun(Base):
    """One row per ``POST /picks`` invocation that produced a report."""

    __tablename__ = "picks_history"

    id = Column(String(36), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    match_query = Column(String(255), nullable=False)
    competition = Column(String(255), nullable=True)
    top_n = Column(Integer, nullable=False)
    request_json = Column(Text, nullable=False)
    report_markdown = Column(Text, nullable=False)
    scores_json = Column(Text, nullable=False)
    trace_json = Column(Text, nullable=True)
    fixture_status = Column(String(64), nullable=True)
    llm_status = Column(String(64), nullable=True)
    latency_ms = Column(Integer, nullable=True)


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


def record_pick_run(
    *,
    request_payload: dict[str, Any],
    result: dict[str, Any],
    latency_ms: int,
) -> PickRun:
    """Persist a successful pipeline run and return the stored row."""
    trace = result.get("trace") or {}
    match_inputs = result.get("match_inputs") or {}
    fixture_status = None
    match_meta = match_inputs.get("match") if isinstance(match_inputs, dict) else None
    if isinstance(match_meta, dict):
        fixture_status = match_meta.get("fixture_status") or match_meta.get("status")

    competition_value = request_payload.get("league") or request_payload.get("competition")
    competition_text = str(competition_value)[:255] if competition_value else None

    row = PickRun(
        id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
        match_query=str(request_payload.get("match_query", ""))[:255],
        competition=competition_text,
        top_n=int(request_payload.get("top_n", 5)),
        request_json=json.dumps(_safe_request_payload(request_payload), default=str),
        report_markdown=str(result.get("report_markdown", "")),
        scores_json=json.dumps(result.get("scores", []), default=str),
        trace_json=json.dumps(trace, default=str) if trace else None,
        fixture_status=fixture_status,
        llm_status=trace.get("llm_status") if isinstance(trace, dict) else None,
        latency_ms=latency_ms,
    )
    with session_scope() as session:
        session.add(row)
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
