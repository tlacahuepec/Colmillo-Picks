"""Catalog refresh policy tests."""

from __future__ import annotations

import json

from services.catalog.contracts import CatalogEvent, CatalogSnapshot, CompletenessStatus
from services.catalog.fanatics_markets import FanaticsCollectionResult
from services.catalog.refresh import run_fanatics_refresh, start_fanatics_refresh
from services.catalog.storage import CatalogStore


def _snapshot(sport: str) -> CatalogSnapshot:
    event = CatalogEvent(
        event_id=f"{sport}:event:1", sport=sport, league=sport,
        start_time="2026-09-19T18:00:00Z",
    )
    return CatalogSnapshot(
        snapshot_id=f"{sport}:snapshot:1", event=event,
        created_at="2026-09-19T12:00:00Z", as_of="2026-09-19T12:00:00Z",
        completeness=CompletenessStatus.PARTIAL,
    )


def test_refresh_registers_disabled_sports_without_persisting_their_events(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    job_id = start_fanatics_refresh(store, run_date="2026-09-19")
    assert job_id is not None

    class FakeCollector:
        def collect(self, *, run_date: str) -> FanaticsCollectionResult:
            assert run_date == "2026-09-19"
            return FanaticsCollectionResult((_snapshot("baseball"), _snapshot("tennis")), 0)

    run_fanatics_refresh(store, job_id=job_id, run_date="2026-09-19", collector_factory=FakeCollector)

    assert [event["event_id"] for event in store.list_events()] == ["baseball:event:1"]
    settings = {item["sport"]: item for item in store.list_sport_settings()}
    assert settings["tennis"]["enabled"] is False
    assert settings["tennis"]["retained_events"] == 0
    assert json.loads(store.get_job(job_id)["summary"])["skipped_by_sport"] == {"tennis": 1}
