from services.catalog.contracts import SourceObservation
from services.catalog.providers import ProviderResult, ProviderStatus
from services.catalog.sport_adapters import NflCatalogAdapter


class FakeProvider:
    provider_name = "nfl-fixture"

    def __init__(self, facts):
        self.facts = facts

    def fetch(self, request):
        return ProviderResult(
            provider=self.provider_name, status=ProviderStatus.AVAILABLE,
            retrieved_at="2026-09-11T12:00:00Z", facts=self.facts,
            observation=SourceObservation(f"obs:{request.resource}", self.provider_name, "2026-09-11T12:00:00Z"),
        )


def test_nfl_adapter_preserves_game_and_player_prop_facts():
    adapter = NflCatalogAdapter(
        schedule_provider=FakeProvider({"matches": [{"id": "nfl-7", "home": "Home", "away": "Away", "start_time": "2026-09-11T18:00:00Z"}]}),
        providers={"lineups": FakeProvider({"lineups": [{"team_id": "home", "players": [{"id": "qb1", "name": "Quarterback"}]}]}), "injuries": FakeProvider({"injuries": [{"player_id": "rb1", "player": "Running Back", "status": "questionable"}]}), "markets": FakeProvider({"moneyline": {"home": -120}, "player_props": [{"player_id": "qb1", "market": "passing_touchdowns"}]})},
        clock=lambda: "2026-09-11T12:00:00Z",
    )
    event = adapter.discover("2026-09-11")[0]
    snapshot = adapter.normalize(event, adapter.collect(event))
    assert event.event_id == "nfl:event:nfl-7"
    assert snapshot.field("player_props") is not None
    assert snapshot.injuries[0].subject.canonical_id == "nfl:player:rb1"
