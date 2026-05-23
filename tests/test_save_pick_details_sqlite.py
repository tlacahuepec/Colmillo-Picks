"""Persistence tests for saved pick details in SqliteRunLedger."""

from __future__ import annotations

from pathlib import Path

import pytest

from run_ledger import SqliteRunLedger

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
]


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "runs.db"


class TestSqlitePickPersistence:
    def test_picks_persist_across_instances(self, db_path: Path) -> None:
        ledger1 = SqliteRunLedger(db_path=str(db_path))
        ctx = ledger1.start_run(source="cli", request={"match_query": "a - b today"})
        ledger1.save_picks(ctx.id, SAMPLE_PICKS)

        ledger2 = SqliteRunLedger(db_path=str(db_path))
        picks = ledger2.get_picks(ctx.id)

        assert len(picks) == 1
        assert picks[0].player == "Arsenal CM"
        assert picks[0].risk_notes == ["lineup_unconfirmed:Arsenal"]
