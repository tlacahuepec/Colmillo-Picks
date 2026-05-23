"""Persistence tests for SqliteRunLedger."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from run_ledger import SqliteRunLedger


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "runs.db"


class TestSqlitePersistence:
    def test_creates_table_on_init(self, db_path: Path) -> None:
        SqliteRunLedger(db_path=str(db_path))

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='run_ledger'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_persists_across_instances(self, db_path: Path) -> None:
        ledger1 = SqliteRunLedger(db_path=str(db_path))
        ctx = ledger1.start_run(source="cli", request={"match_query": "a - b today"})
        ledger1.complete_run(ctx.id)

        ledger2 = SqliteRunLedger(db_path=str(db_path))
        retrieved = ledger2.get_run(ctx.id)

        assert retrieved is not None
        assert retrieved.id == ctx.id
        assert retrieved.status == "success"
        assert retrieved.completed_at is not None
        assert retrieved.duration_ms is not None
