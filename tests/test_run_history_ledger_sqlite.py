"""Persistence tests for run history listing in SqliteRunLedger."""

from __future__ import annotations

from pathlib import Path

import pytest

from run_ledger import SqliteRunLedger


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "runs.db"


class TestSqliteListRuns:
    def test_list_runs_persists_across_instances(self, db_path: Path) -> None:
        ledger1 = SqliteRunLedger(db_path=str(db_path))
        ledger1.start_run(source="cli", request={"match_query": "a - b today"})
        ledger1.start_run(source="api", request={"match_query": "c - d today"})

        ledger2 = SqliteRunLedger(db_path=str(db_path))
        runs = ledger2.list_runs()
        assert len(runs) == 2

    def test_list_runs_most_recent_first_sqlite(self, db_path: Path) -> None:
        ledger = SqliteRunLedger(db_path=str(db_path))
        ctx1 = ledger.start_run(source="cli", request={"match_query": "a - b today"})
        ctx2 = ledger.start_run(source="cli", request={"match_query": "c - d today"})

        runs = ledger.list_runs()
        assert runs[0].id == ctx2.id
        assert runs[1].id == ctx1.id

    def test_list_runs_excludes_request_snapshot_sqlite(self, db_path: Path) -> None:
        ledger = SqliteRunLedger(db_path=str(db_path))
        ledger.start_run(source="cli", request={"match_query": "a - b today", "llm_provider": "gemini"})

        runs = ledger.list_runs()
        assert runs[0].request_snapshot == {}
