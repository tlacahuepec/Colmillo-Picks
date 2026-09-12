from services.catalog.contracts import SourceObservation
from services.catalog.providers import ProviderResult, ProviderStatus
from services.catalog.sport_adapters import BasketballCatalogAdapter


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


def test_basketball_adapter_uses_basketball_canonical_ids():
    adapter = BasketballCatalogAdapter(
        schedule_provider=FakeProvider({"matches": [{"id": "7", "home": "Home", "away": "Away", "start_time": "2026-09-11T18:00:00Z"}]}),
        providers={"lineups": FakeProvider({"lineups": [{"team_id": "home", "players": [{"id": "p1", "name": "Guard"}]}]}), "injuries": FakeProvider({"injuries": []}), "markets": FakeProvider({"spread": -2.5})},
        clock=lambda: "2026-09-11T12:00:00Z",
    )
    event = adapter.discover("2026-09-11")[0]
    snapshot = adapter.normalize(event, adapter.collect(event))
    assert event.event_id == "basketball:event:7"
    assert snapshot.lineups[0].players[0].canonical_id == "basketball:player:p1"
    assert "form" in snapshot.missing_fields
