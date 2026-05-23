"""Unit tests for saving final pick details to the run ledger."""

from __future__ import annotations

import pytest

from run_ledger import InMemoryRunLedger


@pytest.fixture
def ledger() -> InMemoryRunLedger:
    return InMemoryRunLedger()


SAMPLE_PICKS = [
    {
        "player": "Arsenal CM",
        "team_id": "ARS",
        "market": "passes",
        "line": 61.5,
        "direction": "over",
        "score": 0.72,
        "confidence": "medium",
        "explainability": {"risk_flags": ["lineup_unconfirmed:Arsenal"]},
    },
    {
        "player": "Liverpool CB",
        "team_id": "LIV",
        "market": "passes",
        "line": 64.5,
        "direction": "under",
        "score": 0.55,
        "confidence": "low",
        "explainability": {"risk_flags": []},
    },
]


class TestSavePicks:
    def test_successful_run_saves_final_picks(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})

        ledger.save_picks(ctx.id, SAMPLE_PICKS)

        picks = ledger.get_picks(ctx.id)
        assert len(picks) == 2

    def test_saved_picks_use_correct_run_id(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})
        ledger.save_picks(ctx.id, SAMPLE_PICKS)

        picks = ledger.get_picks(ctx.id)
        assert all(p.run_id == ctx.id for p in picks)

    def test_saved_picks_include_rank(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})
        ledger.save_picks(ctx.id, SAMPLE_PICKS)

        picks = ledger.get_picks(ctx.id)
        assert picks[0].rank == 1
        assert picks[1].rank == 2

    def test_saved_picks_include_core_fields(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})
        ledger.save_picks(ctx.id, SAMPLE_PICKS)

        pick = ledger.get_picks(ctx.id)[0]
        assert pick.player == "Arsenal CM"
        assert pick.team_id == "ARS"
        assert pick.market == "passes"
        assert pick.line == 61.5
        assert pick.direction == "over"
        assert pick.score == 0.72
        assert pick.confidence == "medium"

    def test_saved_picks_include_risk_notes(self, ledger: InMemoryRunLedger) -> None:
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today"})
        ledger.save_picks(ctx.id, SAMPLE_PICKS)

        pick = ledger.get_picks(ctx.id)[0]
        assert pick.risk_notes == ["lineup_unconfirmed:Arsenal"]

    def test_get_picks_returns_empty_for_unknown_run(self, ledger: InMemoryRunLedger) -> None:
        assert ledger.get_picks("nonexistent") == []
