from datetime import datetime, timezone

from services.catalog.contracts import CatalogEvent, CatalogField, CatalogSnapshot, FreshnessStatus, LineupSnapshot, Confidence
from services.catalog.freshness import evaluate_field, resources_to_refresh


NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)
EVENT = CatalogEvent("nfl:event:1", "nfl", "nfl", "2026-09-11T18:00:00Z")


def test_field_ttls_are_independent():
    fresh_market = CatalogField("markets", {}, "2026-09-11T11:50:00Z")
    stale_form = CatalogField("form", {}, "2026-09-10T11:00:00Z")
    assert evaluate_field(fresh_market, now=NOW).status == FreshnessStatus.FRESH
    assert evaluate_field(stale_form, now=NOW).status == FreshnessStatus.STALE
    assert evaluate_field(stale_form, now=NOW).should_refresh


def test_expiry_and_unknown_timestamps_refresh_safely():
    expired = CatalogField("weather", {}, "2026-09-11T03:00:00Z")
    unknown = CatalogField("markets", {}, None)
    assert evaluate_field(expired, now=NOW).status == FreshnessStatus.EXPIRED
    assert evaluate_field(unknown, now=NOW).status == FreshnessStatus.UNKNOWN
    assert evaluate_field(unknown, now=NOW).should_refresh


def test_snapshot_returns_unique_stale_resources():
    snapshot = CatalogSnapshot(
        "s1", EVENT, "2026-09-11T11:00:00Z", "2026-09-11T11:00:00Z",
        fields=(CatalogField("markets", {}, "2026-09-11T11:00:00Z"),
                CatalogField("form.home", {}, "2026-09-10T11:00:00Z")),
        lineups=(LineupSnapshot("nfl:event:1", "nfl:team:home", Confidence.CONFIRMED,
                                observed_at="2026-09-11T09:00:00Z"),),
    )
    assert resources_to_refresh(snapshot, now=NOW) == ("form.home", "lineups", "markets")
