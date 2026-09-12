from services.catalog.contracts import SourceObservation
from services.catalog.providers import ProviderResult, ProviderStatus
from services.catalog.sport_adapters import MlbCatalogAdapter


class FakeProvider:
    provider_name = "statsapi-fixture"

    def __init__(self, facts):
        self.facts = facts

    def fetch(self, request):
        return ProviderResult(
            provider=self.provider_name, status=ProviderStatus.AVAILABLE,
            retrieved_at="2026-09-11T12:00:00Z", facts=self.facts,
            observation=SourceObservation(f"obs:{request.resource}", self.provider_name, "2026-09-11T12:00:00Z"),
        )


def test_mlb_adapter_normalizes_baseball_schedule_and_pitcher_facts():
    adapter = MlbCatalogAdapter(
        schedule_provider=FakeProvider({"matches": [{"id": "mlb-7", "home": "Home", "away": "Away", "start_time": "2026-09-11T18:00:00Z"}]}),
        providers={"lineups": FakeProvider({"lineups": [{"team_id": "home", "players": [{"id": "p1", "name": "Starter"}]}]}), "injuries": FakeProvider({"injuries": []}), "markets": FakeProvider({"moneyline": {"home": -110}}), "form": FakeProvider({"pitching": {"home": "good"}})},
        clock=lambda: "2026-09-11T12:00:00Z",
    )
    event = adapter.discover("2026-09-11")[0]
    snapshot = adapter.normalize(event, adapter.collect(event))
    assert event.event_id == "baseball:event:mlb-7"
    assert event.league == "mlb"
    assert snapshot.field("pitching") is not None
    assert snapshot.lineups[0].players[0].canonical_id == "baseball:player:p1"
