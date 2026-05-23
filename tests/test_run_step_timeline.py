"""Unit tests for run step timeline recording."""

from __future__ import annotations

import pytest

from run_ledger import InMemoryRunLedger


@pytest.fixture
def ledger() -> InMemoryRunLedger:
    return InMemoryRunLedger()


class TestRecordStep:
    def test_records_step_with_correct_run_id(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        ledger.record_step(ctx.id, "parse", status="success", duration_ms=12)

        steps = ledger.get_steps(ctx.id)
        assert len(steps) == 1
        assert steps[0].run_id == ctx.id

    def test_records_step_name_and_duration(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        ledger.record_step(ctx.id, "collect", status="success", duration_ms=250)

        steps = ledger.get_steps(ctx.id)
        assert steps[0].step_name == "collect"
        assert steps[0].duration_ms == 250
        assert steps[0].status == "success"

    def test_records_step_with_failed_status(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        ledger.record_step(ctx.id, "score", status="failed", duration_ms=5)

        steps = ledger.get_steps(ctx.id)
        assert steps[0].status == "failed"

    def test_records_step_timestamp(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        ledger.record_step(ctx.id, "parse", status="success", duration_ms=10)

        steps = ledger.get_steps(ctx.id)
        assert steps[0].started_at is not None

    def test_multiple_steps_preserve_order(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        ledger.record_step(ctx.id, "parse", status="success", duration_ms=5)
        ledger.record_step(ctx.id, "collect", status="success", duration_ms=100)
        ledger.record_step(ctx.id, "score", status="success", duration_ms=30)

        steps = ledger.get_steps(ctx.id)
        assert len(steps) == 3
        assert [s.step_name for s in steps] == ["parse", "collect", "score"]

    def test_get_steps_returns_empty_for_unknown_run(self, ledger: InMemoryRunLedger) -> None:
        assert ledger.get_steps("nonexistent") == []
