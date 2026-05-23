"""Persistence tests for partial run outcomes in SqliteRunLedger."""

from __future__ import annotations

from pathlib import Path

import pytest

from run_ledger import SqliteRunLedger


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "runs.db"


class TestSqlitePartialRun:
    def test_partial_run_persists_across_instances(self, db_path: Path) -> None:
        ledger1 = SqliteRunLedger(db_path=str(db_path))
        ctx = ledger1.start_run(source="cli", request={"match_query": "a - b today"})
        ledger1.partial_run(ctx.id, reasons=["LLM failed", "Availability unavailable"])

        ledger2 = SqliteRunLedger(db_path=str(db_path))
        retrieved = ledger2.get_run(ctx.id)

        assert retrieved is not None
        assert retrieved.status == "partial"
        assert retrieved.partial_reasons == ["LLM failed", "Availability unavailable"]
