"""Persistence tests for run step timeline in SqliteRunLedger."""

from __future__ import annotations

from pathlib import Path

import pytest

from run_ledger import SqliteRunLedger


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "runs.db"


class TestSqliteStepPersistence:
    def test_steps_persist_across_instances(self, db_path: Path) -> None:
        ledger1 = SqliteRunLedger(db_path=str(db_path))
        ctx = ledger1.start_run(source="cli", request={"match_query": "a - b today"})
        ledger1.record_step(ctx.id, "parse", status="success", duration_ms=8)
        ledger1.record_step(ctx.id, "collect", status="success", duration_ms=150)

        ledger2 = SqliteRunLedger(db_path=str(db_path))
        steps = ledger2.get_steps(ctx.id)

        assert len(steps) == 2
        assert steps[0].step_name == "parse"
        assert steps[0].duration_ms == 8
        assert steps[1].step_name == "collect"
        assert steps[1].duration_ms == 150

    def test_steps_table_created_on_init(self, db_path: Path) -> None:
        import sqlite3

        SqliteRunLedger(db_path=str(db_path))

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='run_steps'"
        )
        assert cursor.fetchone() is not None
        conn.close()
