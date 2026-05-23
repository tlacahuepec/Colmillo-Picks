"""Tests for run history listing on the RunLedger."""

from __future__ import annotations

import pytest

from run_ledger import InMemoryRunLedger


@pytest.fixture
def ledger() -> InMemoryRunLedger:
    return InMemoryRunLedger()


class TestListRuns:
    def test_list_runs_returns_empty_when_no_runs(self, ledger: InMemoryRunLedger) -> None:
        assert ledger.list_runs() == []

    def test_list_runs_returns_all_runs(self, ledger: InMemoryRunLedger) -> None:
        ledger.start_run(source="cli", request={"match_query": "a - b today"})
        ledger.start_run(source="api", request={"match_query": "c - d tomorrow"})

        runs = ledger.list_runs()
        assert len(runs) == 2

    def test_list_runs_respects_limit(self, ledger: InMemoryRunLedger) -> None:
        for i in range(5):
            ledger.start_run(source="cli", request={"match_query": f"team{i} - rival today"})

        runs = ledger.list_runs(limit=3)
        assert len(runs) == 3

    def test_list_runs_respects_offset(self, ledger: InMemoryRunLedger) -> None:
        ids = []
        for i in range(5):
            ctx = ledger.start_run(source="cli", request={"match_query": f"team{i} - rival today"})
            ids.append(ctx.id)

        runs = ledger.list_runs(offset=2)
        assert len(runs) == 3

    def test_list_runs_most_recent_first(self, ledger: InMemoryRunLedger) -> None:
        ctx1 = ledger.start_run(source="cli", request={"match_query": "a - b today"})
        ctx2 = ledger.start_run(source="cli", request={"match_query": "c - d today"})

        runs = ledger.list_runs()
        assert runs[0].id == ctx2.id
        assert runs[1].id == ctx1.id

    def test_list_runs_does_not_include_request_snapshot(self, ledger: InMemoryRunLedger) -> None:
        ledger.start_run(source="cli", request={"match_query": "a - b today", "llm_provider": "gemini"})

        runs = ledger.list_runs()
        assert runs[0].request_snapshot == {}
