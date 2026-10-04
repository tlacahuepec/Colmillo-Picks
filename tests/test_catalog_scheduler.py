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


def test_concurrent_lease_claims_only_one_winner(tmp_path):
    import concurrent.futures
    import threading

    store = CatalogStore(tmp_path / "catalog.db")
    scheduler = CatalogScheduler(store)
    num_threads = 10
    barrier = threading.Barrier(num_threads)

    def worker():
        barrier.wait()
        return scheduler.claim(now=AFTER)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker) for _ in range(num_threads)]
        results = [f.result() for f in futures]

    claims = [r for r in results if r is not None]
    assert len(claims) == 1
    winner = claims[0]
    job = store.get_job(winner)
    assert job is not None
    assert job["state"] == "running"
    assert job["attempt"] == 1


def test_concurrent_expired_lease_reclaim_under_contention(tmp_path):
    import concurrent.futures
    import threading

    store = CatalogStore(tmp_path / "catalog.db")
    scheduler = CatalogScheduler(store, lease_minutes=1)
    first_job = scheduler.claim(now=AFTER)
    assert first_job is not None

    later = datetime(2026, 9, 11, 7, 0, tzinfo=timezone.utc)
    num_threads = 10
    barrier = threading.Barrier(num_threads)

    def worker():
        barrier.wait()
        return scheduler.claim(now=later)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker) for _ in range(num_threads)]
        results = [f.result() for f in futures]

    claims = [r for r in results if r is not None]
    assert len(claims) == 1
    winner = claims[0]
    assert winner != first_job
    job = store.get_job(winner)
    assert job is not None
    assert job["attempt"] == 2


def test_heartbeat_extends_lease_and_blocks_stealing(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    scheduler = CatalogScheduler(store, lease_minutes=2)
    job = scheduler.claim(now=AFTER)
    assert job is not None

    t1 = datetime(2026, 9, 11, 6, 2, tzinfo=timezone.utc)
    assert scheduler.heartbeat(job, now=t1)

    t2 = datetime(2026, 9, 11, 6, 3, 30, tzinfo=timezone.utc)
    competitor = scheduler.claim(now=t2)
    assert competitor is None, "Competitor should not steal heartbeated active lease"

    t3 = datetime(2026, 9, 11, 6, 4, 1, tzinfo=timezone.utc)
    competitor = scheduler.claim(now=t3)
    assert competitor is not None, "Competitor can claim once heartbeated lease expires"
    assert store.get_job(competitor)["attempt"] == 2


def test_reclaim_after_failed_attempt(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    scheduler = CatalogScheduler(store)
    job = scheduler.claim(now=AFTER)
    assert job is not None
    scheduler.finish(job, "failed", summary="worker crashed", now=AFTER)

    retry_time = datetime(2026, 9, 11, 6, 30, tzinfo=timezone.utc)
    retry_job = scheduler.claim(now=retry_time)
    assert retry_job is not None
    assert retry_job != job
    assert store.get_job(retry_job)["attempt"] == 2

