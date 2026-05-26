"""Tests for the worker resolution cycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from services.api import db as db_module
from services.api.db import (
    PickRun,
    create_pending_pick_run,
    mark_pick_success,
    session_scope,
)
from services.worker.main import run_resolution_cycle


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    db_module.configure_engine(f"sqlite:///{tmp_path / 'test-worker.db'}")


def _make_successful_pick_with_kickoff(*, hours_ago: int = 4) -> PickRun:
    row = create_pending_pick_run(
        request_payload={"match_query": "NYY vs BOS", "top_n": 3}
    )
    mark_pick_success(
        pick_id=row.id,
        result={
            "report_markdown": "# Test",
            "scores": [
                {"rank": 1, "player": "Judge", "market": "hits", "line": 1.5, "direction": "over"}
            ],
            "trace": {},
        },
        latency_ms=100,
    )
    kickoff = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    with session_scope() as session:
        run = session.get(PickRun, row.id)
        run.scheduled_kickoff_utc = kickoff
        session.add(run)
    return row


class TestRunResolutionCycle:
    @patch("services.worker.main._attempt_resolution")
    def test_calls_attempt_for_unresolved_picks(self, mock_attempt):
        _make_successful_pick_with_kickoff(hours_ago=5)

        resolved = run_resolution_cycle()

        assert mock_attempt.call_count == 1
        assert resolved == 1

    @patch("services.worker.main._attempt_resolution")
    def test_skips_recent_picks(self, mock_attempt):
        _make_successful_pick_with_kickoff(hours_ago=1)

        resolved = run_resolution_cycle()

        assert mock_attempt.call_count == 0
        assert resolved == 0

    @patch("services.worker.main._attempt_resolution")
    def test_handles_resolution_error_gracefully(self, mock_attempt):
        mock_attempt.side_effect = RuntimeError("LLM unavailable")
        _make_successful_pick_with_kickoff(hours_ago=5)

        resolved = run_resolution_cycle()

        assert resolved == 0
