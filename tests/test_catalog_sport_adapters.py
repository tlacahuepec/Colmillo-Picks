"""Tests for provider-backed catalog sport adapters."""

from services.catalog.contracts import SourceObservation
from services.catalog.providers import ProviderResult, ProviderStatus
from services.catalog.sport_adapters import SoccerCatalogAdapter


class FakeProvider:
    provider_name = "fixture"

    def __init__(self, facts):
        self.facts = facts

    def fetch(self, request):
        return ProviderResult(
            provider=self.provider_name, status=ProviderStatus.AVAILABLE,
            retrieved_at="2026-09-11T12:00:00Z", facts=self.facts,
            observation=SourceObservation(f"obs:{request.resource}", self.provider_name, "2026-09-11T12:00:00Z"),
        )


def test_soccer_adapter_normalizes_schedule_and_intelligence():
    adapter = SoccerCatalogAdapter(
        schedule_provider=FakeProvider({"matches": [{"id": "42", "home": "A", "away": "B", "start_time": "2026-09-11T18:00:00Z"}]}),
        providers={
            "lineups": FakeProvider({"lineups": [{"team_id": "a", "status": "confirmed", "players": [{"id": "p1", "name": "Player"}]}]}),
            "injuries": FakeProvider({"injuries": [{"player_id": "p2", "player": "Out", "status": "out"}]}),
            "markets": FakeProvider({"odds": {"home": 1.8}}),
        },
        clock=lambda: "2026-09-11T12:00:00Z",
    )
    event = adapter.discover("2026-09-11")[0]
    snapshot = adapter.normalize(event, adapter.collect(event))
    assert event.event_id == "soccer:event:42"
    assert len(snapshot.lineups) == 1
    assert len(snapshot.injuries) == 1
    assert snapshot.field("odds") is not None
    assert snapshot.missing_fields == ("form", "weather")
    assert adapter.validate(snapshot) == ["form", "weather"]
