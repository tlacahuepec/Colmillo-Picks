"""Persistence tests for the local sports catalog."""

from services.catalog.contracts import CatalogEvent, CatalogSnapshot, CompletenessStatus, SourceObservation
from services.catalog.storage import CatalogStore


def make_snapshot(snapshot_id="snapshot-1", created_at="2026-09-11T12:00:00+00:00"):
    event = CatalogEvent("nfl:event:1", "nfl", "nfl", "2026-09-11T19:00:00Z")
    return CatalogSnapshot(
        snapshot_id, event, created_at, created_at,
        completeness=CompletenessStatus.COMPLETE,
        source_observations=(SourceObservation("obs-1", "fixture-provider", created_at),),
    )


def test_store_is_idempotent_and_preserves_immutable_snapshots(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    first = make_snapshot()
    store.save_snapshot(first)
    store.save_snapshot(first)
    store.save_snapshot(make_snapshot("snapshot-2", "2026-09-11T13:00:00+00:00"))
    assert store.get_snapshot("snapshot-1")["snapshot_id"] == "snapshot-1"
    assert store.get_latest_snapshot("nfl:event:1")["snapshot_id"] == "snapshot-2"
    assert store.health() == {"available": True, "path": str(tmp_path / "catalog.db"),
                              "events": 1, "snapshots": 2, "observations": 1}


def test_event_listing_filters_and_paginates(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    store.save_snapshot(make_snapshot())
    soccer = CatalogEvent("soccer:event:1", "soccer", "epl", "2026-09-12T18:00:00Z")
    store.upsert_event(soccer)
    assert [event["event_id"] for event in store.list_events(sport="soccer")] == ["soccer:event:1"]
    assert store.list_events(limit=1, offset=1)[0]["event_id"] == "soccer:event:1"
