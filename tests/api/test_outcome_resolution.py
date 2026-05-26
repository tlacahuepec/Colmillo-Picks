"""Tests for outcome resolution DB queries and scheduling logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.api import db as db_module
from services.api.db import (
    PickRun,
    create_pending_pick_run,
    list_unresolved_picks,
    mark_pick_success,
    record_outcomes,
    session_scope,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    db_module.configure_engine(f"sqlite:///{tmp_path / 'test-resolution.db'}")


def _make_successful_pick(*, kickoff_utc: datetime | None = None) -> PickRun:
    row = create_pending_pick_run(request_payload={"match_query": "NYY vs BOS", "top_n": 3})
    mark_pick_success(
        pick_id=row.id,
        result={"report_markdown": "# Test", "scores": [{"player": "Judge"}], "trace": {}},
        latency_ms=100,
    )
    if kickoff_utc:
        with session_scope() as session:
            run = session.get(PickRun, row.id)
            run.scheduled_kickoff_utc = kickoff_utc
            session.add(run)
    return row


class TestListUnresolvedPicks:
    def test_returns_picks_past_kickoff_without_outcomes(self):
        past_kickoff = datetime.now(timezone.utc) - timedelta(hours=4)
        pick = _make_successful_pick(kickoff_utc=past_kickoff)

        settled_before = datetime.now(timezone.utc) - timedelta(hours=3)
        unresolved = list_unresolved_picks(settled_before=settled_before)

        assert len(unresolved) == 1
        assert unresolved[0].id == pick.id

    def test_excludes_picks_with_outcomes(self):
        past_kickoff = datetime.now(timezone.utc) - timedelta(hours=4)
        pick = _make_successful_pick(kickoff_utc=past_kickoff)
        record_outcomes(
            pick_id=pick.id,
            outcomes=[{"rank": 1, "player": "Judge", "market": "hits", "result": "win"}],
        )

        settled_before = datetime.now(timezone.utc) - timedelta(hours=3)
        unresolved = list_unresolved_picks(settled_before=settled_before)

        assert len(unresolved) == 0

    def test_excludes_picks_without_kickoff(self):
        _make_successful_pick(kickoff_utc=None)

        settled_before = datetime.now(timezone.utc) - timedelta(hours=3)
        unresolved = list_unresolved_picks(settled_before=settled_before)

        assert len(unresolved) == 0

    def test_excludes_picks_not_yet_settled(self):
        future_kickoff = datetime.now(timezone.utc) + timedelta(hours=1)
        _make_successful_pick(kickoff_utc=future_kickoff)

        settled_before = datetime.now(timezone.utc) - timedelta(hours=3)
        unresolved = list_unresolved_picks(settled_before=settled_before)

        assert len(unresolved) == 0

    def test_excludes_failed_picks(self):
        past_kickoff = datetime.now(timezone.utc) - timedelta(hours=4)
        row = create_pending_pick_run(request_payload={"match_query": "test", "top_n": 3})
        with session_scope() as session:
            run = session.get(PickRun, row.id)
            run.scheduled_kickoff_utc = past_kickoff
            session.add(run)

        settled_before = datetime.now(timezone.utc) - timedelta(hours=3)
        unresolved = list_unresolved_picks(settled_before=settled_before)

        assert len(unresolved) == 0
