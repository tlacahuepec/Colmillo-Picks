"""Contract tests for the daily sports intelligence catalog."""

import json

import pytest

from services.catalog.contracts import (
    CanonicalRef,
    CatalogEvent,
    CatalogField,
    CatalogSnapshot,
    CompletenessStatus,
    Confidence,
    FreshnessStatus,
    LineupSnapshot,
    SourceObservation,
    to_catalog_dict,
)


def test_snapshot_is_immutable_and_json_serializable():
    team = CanonicalRef("team", "nfl:team:saints", "New Orleans Saints", {"provider": "NO"})
    event = CatalogEvent("nfl:event:1", "nfl", "nfl", "2026-09-11T19:00:00Z", home_team=team)
    observation = SourceObservation("obs-1", "provider", "2026-09-11T12:00:00Z", confidence=Confidence.CONFIRMED)
    snapshot = CatalogSnapshot(
        "snapshot-1", event, "2026-09-11T12:00:01Z", "2026-09-11T12:00:00Z",
        completeness=CompletenessStatus.PARTIAL,
        fields=(CatalogField("weather", {"temperature_c": 20}, freshness=FreshnessStatus.FRESH),),
        lineups=(LineupSnapshot("nfl:event:1", team.canonical_id, Confidence.PROJECTED),),
        source_observations=(observation,), missing_fields=("injuries",),
    )
    payload = to_catalog_dict(snapshot)
    encoded = json.loads(json.dumps(payload))
    assert encoded["schema_version"] == 1
    assert snapshot.field("weather").freshness == FreshnessStatus.FRESH
    with pytest.raises((AttributeError, TypeError)):
        snapshot.snapshot_id = "changed"


def test_contract_preserves_conflicts_and_unknowns():
    snapshot = CatalogSnapshot(
        "snapshot-2",
        CatalogEvent("soccer:event:1", "soccer", "epl", "2026-09-11T18:00:00Z"),
        "2026-09-11T12:00:00Z", "2026-09-11T12:00:00Z",
        completeness=CompletenessStatus.CONFLICTING,
        fields=(CatalogField("lineup", None, freshness=FreshnessStatus.UNKNOWN,
                             confidence=Confidence.UNKNOWN, conflict_group="lineup-1"),),
        conflicting_fields=("lineup",),
    )
    assert snapshot.completeness == CompletenessStatus.CONFLICTING
    assert snapshot.field("lineup").conflict_group == "lineup-1"


def test_to_catalog_dict_rejects_arbitrary_objects():
    with pytest.raises(TypeError, match="not JSON-compatible"):
        to_catalog_dict(object())
