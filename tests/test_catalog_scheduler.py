"""Durable schedule, lease and checkpoint tests."""

from datetime import datetime, timezone

import pytest

from services.catalog.scheduler import CatalogScheduler, DailySchedule
from services.catalog.storage import CatalogStore


BEFORE = datetime(2026, 9, 11, 5, 59, tzinfo=timezone.utc)
AFTER = datetime(2026, 9, 11, 6, 1, tzinfo=timezone.utc)


def test_schedule_is_due_only_after_configured_time(tmp_path):
    scheduler = CatalogScheduler(CatalogStore(tmp_path / "catalog.db"), schedule=DailySchedule(6, 0))
    assert not scheduler.due(BEFORE)
    assert scheduler.due(AFTER)


def test_lease_allows_one_run_and_blocks_duplicate(tmp_path):
    scheduler = CatalogScheduler(CatalogStore(tmp_path / "catalog.db"))
    first = scheduler.claim(now=AFTER)
    assert first
    assert scheduler.claim(now=AFTER) is None
    assert scheduler.checkpoint(first, "rank_events", now=AFTER)
    assert scheduler.store.get_job(first)["checkpoint"] == "rank_events"


def test_expired_lease_can_be_reclaimed_and_attempt_increments(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    scheduler = CatalogScheduler(store, lease_minutes=1)
    first = scheduler.claim(now=AFTER)
    later = datetime(2026, 9, 11, 7, 0, tzinfo=timezone.utc)
    second = scheduler.claim(now=later)
    assert first and second and first != second
    assert store.get_job(second)["attempt"] == 2


def test_successful_date_cannot_be_reclaimed(tmp_path):
    scheduler = CatalogScheduler(CatalogStore(tmp_path / "catalog.db"))
    job = scheduler.claim(now=AFTER)
    assert scheduler.finish(job, "success", summary="published", now=AFTER)
    assert scheduler.claim(now=datetime(2026, 9, 11, 8, tzinfo=timezone.utc)) is None


def test_terminal_state_is_validated(tmp_path):
    scheduler = CatalogScheduler(CatalogStore(tmp_path / "catalog.db"))
    job = scheduler.claim(now=AFTER)
    with pytest.raises(ValueError, match="terminal state"):
        scheduler.finish(job, "queued", now=AFTER)
