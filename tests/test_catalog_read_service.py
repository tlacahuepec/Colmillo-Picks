from datetime import datetime, timezone

from services.catalog.contracts import CatalogEvent, CatalogField, CatalogSnapshot
from services.catalog.read_service import CatalogFirstReader


def test_catalog_reader_uses_fresh_local_snapshot_without_refresh():
    snapshot = CatalogSnapshot(
        "s1", CatalogEvent("nfl:event:1", "nfl", "nfl", "2026-09-11T18:00:00Z"),
        "2026-09-11T11:50:00Z", "2026-09-11T11:50:00Z",
        fields=(CatalogField("markets", {}, "2026-09-11T11:50:00Z"),),
    )
    refreshes = []
    result = CatalogFirstReader(
        lookup=lambda *args: snapshot,
        refresh=lambda *args: refreshes.append(args),
    ).read(sport="nfl", home_team="A", away_team="B", event_date="2026-09-11",
           requested_resources=(), now=datetime(2026, 9, 11, 12, tzinfo=timezone.utc))
    assert result.source == "catalog"
    assert result.refresh_resources == ()
    assert refreshes == []


def test_catalog_reader_refreshes_only_stale_resources():
    snapshot = CatalogSnapshot(
        "s1", CatalogEvent("nfl:event:1", "nfl", "nfl", "2026-09-11T18:00:00Z"),
        "2026-09-11T10:00:00Z", "2026-09-11T10:00:00Z",
        fields=(CatalogField("markets", {}, "2026-09-11T10:00:00Z"),),
    )
    calls = []
    result = CatalogFirstReader(
        lookup=lambda *args: snapshot,
        refresh=lambda *args: calls.append(args) or snapshot,
    ).read(sport="nfl", home_team="A", away_team="B", event_date="2026-09-11",
           requested_resources=("lineups",), now=datetime(2026, 9, 11, 12, tzinfo=timezone.utc))
    assert result.source == "refreshed"
    assert calls[0][-1] == ("lineups", "markets")
