"""Provider boundary and normalization tests for the sports catalog."""

from services.catalog.contracts import Confidence, FreshnessStatus
from services.catalog.providers import (
    CatalogProvider,
    ProviderRequest,
    ProviderResult,
    ProviderStatus,
    canonical_entity_id,
    merge_field_observations,
    normalize_event,
)


class FakeProvider:
    provider_name = "fake"

    def fetch(self, request):
        return ProviderResult(self.provider_name, ProviderStatus.AVAILABLE, request.requested_at)


def test_provider_port_and_request_result_are_explicit():
    assert isinstance(FakeProvider(), CatalogProvider)
    request = ProviderRequest("nfl", "schedule", "2026-09-11T12:00:00Z", date="2026-09-11")
    result = FakeProvider().fetch(request)
    assert result.status == ProviderStatus.AVAILABLE
    assert result.facts == {}


def test_canonical_ids_are_stable_and_normalized():
    assert canonical_entity_id("NFL", "Team", display_name=" New Orleans Saints ") == "nfl:team:new-orleans-saints"
    assert canonical_entity_id("soccer", "event", provider_id="ABC-123") == "soccer:event:abc-123"


def test_normalize_event_keeps_provider_provenance():
    event, observation = normalize_event(
        raw={"id": "game-1", "home": "Saints", "away": "Lions", "start_time": "2026-09-11T19:00:00Z"},
        sport="nfl", league="nfl", provider="fake", observed_at="2026-09-11T12:00:00Z",
    )
    assert event.event_id == "nfl:event:game-1"
    assert event.home_team.canonical_id == "nfl:team:saints"
    assert observation.provider_record_id == "game-1"


def test_merge_marks_conflicting_values_and_unknown_empty_values():
    first = normalize_event(
        raw={"id": "a", "home": "A", "away": "B", "start_time": "2026-09-11"},
        sport="nfl", league="nfl", provider="one", observed_at="2026-09-11T10:00:00Z",
    )[1]
    second = normalize_event(
        raw={"id": "b", "home": "A", "away": "B", "start_time": "2026-09-11"},
        sport="nfl", league="nfl", provider="two", observed_at="2026-09-11T10:01:00Z",
    )[1]
    conflict = merge_field_observations("lineup", [("projected", first), ("confirmed", second)])
    unknown = merge_field_observations("injuries", [])
    assert conflict.conflict_group == "lineup:conflict"
    assert conflict.confidence == Confidence.UNKNOWN
    assert unknown.freshness == FreshnessStatus.UNKNOWN
