"""Unit tests for RunLedger (InMemoryRunLedger implementation)."""

from __future__ import annotations

import uuid

import pytest

from run_ledger import InMemoryRunLedger


@pytest.fixture
def ledger() -> InMemoryRunLedger:
    return InMemoryRunLedger()


class TestStartRun:
    def test_creates_context_with_stable_id(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        assert ctx.id
        uuid.UUID(ctx.id)  # validates UUID format
        assert ctx.status == "running"
        assert ctx.started_at is not None

    def test_extracts_match_query_from_request(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(
            source="cli",
            request={"match_query": "juve - milan today", "top_n": 3},
        )

        assert ctx.match_query == "juve - milan today"
        assert ctx.source == "cli"

    def test_stores_request_snapshot(self, ledger: InMemoryRunLedger) -> None:
        request = {"match_query": "x - y tomorrow", "top_n": 5, "use_llm": False}
        ctx = ledger.start_run(source="api", request=request)

        assert ctx.request_snapshot == request
        assert ctx.source == "api"


class TestCompleteRun:
    def test_persists_success_status_and_timing(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        result = ledger.complete_run(ctx.id)

        assert result.status == "success"
        assert result.completed_at is not None
        assert result.duration_ms is not None
        assert result.duration_ms >= 0


class TestFailRun:
    def test_persists_failed_status_and_error_summary(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        result = ledger.fail_run(
            ctx.id, error_summary="Parse failed", error_stage="parse"
        )

        assert result.status == "failed"
        assert result.error_summary == "Parse failed"
        assert result.error_stage == "parse"
        assert result.completed_at is not None
        assert result.duration_ms is not None
        assert result.duration_ms >= 0


class TestGetRun:
    def test_returns_none_for_unknown_id(self, ledger: InMemoryRunLedger) -> None:
        assert ledger.get_run("nonexistent") is None

    def test_returns_existing_run(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        retrieved = ledger.get_run(ctx.id)

        assert retrieved is not None
        assert retrieved.id == ctx.id
