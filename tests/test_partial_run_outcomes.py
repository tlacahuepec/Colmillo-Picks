"""Unit tests for partial run outcomes."""

from __future__ import annotations

import pytest

from run_ledger import InMemoryRunLedger


@pytest.fixture
def ledger() -> InMemoryRunLedger:
    return InMemoryRunLedger()


class TestPartialRun:
    def test_partial_run_sets_status(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        result = ledger.partial_run(ctx.id, reasons=["LLM enrichment failed"])

        assert result.status == "partial"

    def test_partial_run_stores_reasons(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        result = ledger.partial_run(ctx.id, reasons=["LLM enrichment failed", "Availability check failed"])

        assert result.partial_reasons == ["LLM enrichment failed", "Availability check failed"]

    def test_partial_run_sets_timing(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        result = ledger.partial_run(ctx.id, reasons=["LLM enrichment failed"])

        assert result.completed_at is not None
        assert result.duration_ms is not None
        assert result.duration_ms >= 0

    def test_complete_run_still_sets_success(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        result = ledger.complete_run(ctx.id)

        assert result.status == "success"
        assert result.partial_reasons == []

    def test_failed_step_triggers_partial_status(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})
        ledger.record_step(ctx.id, "parse", status="success", duration_ms=5)
        ledger.record_step(ctx.id, "collect", status="success", duration_ms=100)
        ledger.record_step(ctx.id, "llm_enrichment", status="failed", duration_ms=200)
        ledger.record_step(ctx.id, "render", status="success", duration_ms=10)

        steps = ledger.get_steps(ctx.id)
        failed_steps = [s for s in steps if s.status == "failed"]
        reasons = [f"{s.step_name} failed" for s in failed_steps]

        assert len(reasons) == 1
        assert reasons[0] == "llm_enrichment failed"
