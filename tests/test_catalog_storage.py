"""Persistence tests for the local sports catalog."""

from services.catalog.contracts import (
    CatalogEvent,
    CatalogSnapshot,
    CompletenessStatus,
    PredictionMarketObservation,
    SourceObservation,
)
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


def test_sport_policy_hides_retained_disabled_events_and_can_restore_them(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    tennis = CatalogEvent("tennis:event:1", "tennis", "tennis", "2026-09-12T18:00:00Z")
    store.upsert_event(tennis)

    settings = {item["sport"]: item for item in store.list_sport_settings()}
    assert settings["tennis"]["enabled"] is False
    assert settings["tennis"]["retained_events"] == 1
    assert store.list_events() == []

    store.set_sport_enabled("tennis", enabled=True)
    assert [event["event_id"] for event in store.list_events()] == ["tennis:event:1"]

    store.set_sport_enabled("tennis", enabled=False)
    assert store.list_events() == []


def test_prediction_market_observations_are_persisted_separately_from_fields(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    snapshot = make_snapshot()
    snapshot = CatalogSnapshot(
        snapshot.snapshot_id, snapshot.event, snapshot.created_at, snapshot.as_of,
        prediction_markets=(PredictionMarketObservation(
            market_id="market-1", market_type="moneyline", selection="Home",
            displayed_price="52%", volume="1000", status="available",
            observed_at=snapshot.created_at, source_url="https://fanaticsmarkets.com/",
        ),),
    )

    store.save_snapshot(snapshot)

    persisted = store.get_snapshot(snapshot.snapshot_id)
    assert persisted["prediction_markets"][0]["displayed_price"] == "52%"
