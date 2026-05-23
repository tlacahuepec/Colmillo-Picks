"""SQLite-backed RunLedger implementation."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_ledger.contract import RunContext, RunStep

_DEFAULT_DB_PATH = os.path.join("data", "runs.db")

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS run_ledger (
    id VARCHAR(36) PRIMARY KEY,
    source VARCHAR(16) NOT NULL,
    match_query VARCHAR(255) NOT NULL DEFAULT '',
    home_team VARCHAR(128),
    away_team VARCHAR(128),
    match_date VARCHAR(10),
    competition VARCHAR(255),
    request_json TEXT,
    status VARCHAR(16) NOT NULL DEFAULT 'running',
    error_summary TEXT,
    error_stage VARCHAR(64),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms INTEGER
)
"""

_CREATE_STEPS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS run_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id VARCHAR(36) NOT NULL,
    step_name VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'success',
    started_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0
)
"""

_ENSURE_PARTIAL_REASONS_COLUMN = """
ALTER TABLE run_ledger ADD COLUMN partial_reasons_json TEXT
"""


class SqliteRunLedger:
    def __init__(self, db_path: str | None = None) -> None:
        resolved_path = db_path or os.environ.get("COLMILLO_RUNS_DB_PATH", _DEFAULT_DB_PATH)
        Path(resolved_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = resolved_path
        self._conn = sqlite3.connect(resolved_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.execute(_CREATE_STEPS_TABLE_SQL)
        self._ensure_partial_reasons_column()
        self._conn.commit()

    def _ensure_partial_reasons_column(self) -> None:
        try:
            self._conn.execute(_ENSURE_PARTIAL_REASONS_COLUMN)
        except sqlite3.OperationalError:
            pass  # column already exists

    def start_run(self, *, source: str, request: dict[str, Any]) -> RunContext:
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        match_query = str(request.get("match_query", ""))
        competition = request.get("competition")
        request_json = json.dumps(request, default=str)

        self._conn.execute(
            """INSERT INTO run_ledger (id, source, match_query, competition, request_json, status, started_at)
               VALUES (?, ?, ?, ?, ?, 'running', ?)""",
            (run_id, source, match_query, competition, request_json, now.isoformat()),
        )
        self._conn.commit()

        return RunContext(
            id=run_id,
            source=source,
            match_query=match_query,
            competition=competition,
            request_snapshot=request,
            status="running",
            started_at=now,
        )

    def complete_run(self, run_id: str) -> RunContext:
        now = datetime.now(timezone.utc)
        row = self._conn.execute("SELECT started_at FROM run_ledger WHERE id = ?", (run_id,)).fetchone()
        started_at = datetime.fromisoformat(row["started_at"])
        duration_ms = max(0, round((now - started_at).total_seconds() * 1000))

        self._conn.execute(
            "UPDATE run_ledger SET status = 'success', completed_at = ?, duration_ms = ? WHERE id = ?",
            (now.isoformat(), duration_ms, run_id),
        )
        self._conn.commit()

        return self._load_run(run_id)

    def partial_run(self, run_id: str, *, reasons: list[str]) -> RunContext:
        now = datetime.now(timezone.utc)
        row = self._conn.execute("SELECT started_at FROM run_ledger WHERE id = ?", (run_id,)).fetchone()
        started_at = datetime.fromisoformat(row["started_at"])
        duration_ms = max(0, round((now - started_at).total_seconds() * 1000))
        reasons_json = json.dumps(reasons)

        self._conn.execute(
            "UPDATE run_ledger SET status = 'partial', partial_reasons_json = ?, completed_at = ?, duration_ms = ? WHERE id = ?",
            (reasons_json, now.isoformat(), duration_ms, run_id),
        )
        self._conn.commit()

        return self._load_run(run_id)

    def fail_run(self, run_id: str, *, error_summary: str, error_stage: str | None = None) -> RunContext:
        now = datetime.now(timezone.utc)
        row = self._conn.execute("SELECT started_at FROM run_ledger WHERE id = ?", (run_id,)).fetchone()
        started_at = datetime.fromisoformat(row["started_at"])
        duration_ms = max(0, round((now - started_at).total_seconds() * 1000))

        self._conn.execute(
            "UPDATE run_ledger SET status = 'failed', error_summary = ?, error_stage = ?, completed_at = ?, duration_ms = ? WHERE id = ?",
            (error_summary, error_stage, now.isoformat(), duration_ms, run_id),
        )
        self._conn.commit()

        return self._load_run(run_id)

    def get_run(self, run_id: str) -> RunContext | None:
        return self._load_run(run_id)

    def record_step(self, run_id: str, step_name: str, *, status: str = "success", duration_ms: int = 0) -> RunStep:
        now = datetime.now(timezone.utc)
        self._conn.execute(
            "INSERT INTO run_steps (run_id, step_name, status, started_at, duration_ms) VALUES (?, ?, ?, ?, ?)",
            (run_id, step_name, status, now.isoformat(), duration_ms),
        )
        self._conn.commit()
        return RunStep(
            run_id=run_id,
            step_name=step_name,
            status=status,
            started_at=now,
            duration_ms=duration_ms,
        )

    def get_steps(self, run_id: str) -> list[RunStep]:
        rows = self._conn.execute(
            "SELECT run_id, step_name, status, started_at, duration_ms FROM run_steps WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return [
            RunStep(
                run_id=row["run_id"],
                step_name=row["step_name"],
                status=row["status"],
                started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                duration_ms=row["duration_ms"],
            )
            for row in rows
        ]

    def _load_run(self, run_id: str) -> RunContext | None:
        row = self._conn.execute("SELECT * FROM run_ledger WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None

        request_snapshot: dict[str, Any] = {}
        if row["request_json"]:
            try:
                request_snapshot = json.loads(row["request_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        started_at = datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
        completed_at = datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None

        partial_reasons: list[str] = []
        raw_reasons = row["partial_reasons_json"]
        if raw_reasons:
            try:
                partial_reasons = json.loads(raw_reasons)
            except (json.JSONDecodeError, TypeError):
                pass

        return RunContext(
            id=row["id"],
            source=row["source"],
            match_query=row["match_query"] or "",
            home_team=row["home_team"],
            away_team=row["away_team"],
            match_date=row["match_date"],
            competition=row["competition"],
            request_snapshot=request_snapshot,
            status=row["status"],
            error_summary=row["error_summary"],
            error_stage=row["error_stage"],
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=row["duration_ms"],
            partial_reasons=partial_reasons,
        )
