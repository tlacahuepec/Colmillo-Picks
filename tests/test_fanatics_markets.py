from __future__ import annotations

import json

import httpx
import pytest

from services.catalog.fanatics_markets import FanaticsMarketsCollector, FanaticsMarketsError


class FakeClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    def get(self, *_args, **_kwargs) -> httpx.Response:
        return self.response


def test_collects_typed_prediction_markets_from_public_embedded_json() -> None:
    html = """
    <script type="application/json">
      {"eventId":"mlb-1","sport":"baseball","league":"MLB",
       "homeTeam":"New York Yankees","awayTeam":"Boston Red Sox",
       "startTime":"2026-09-15T19:00:00Z","markets":[{
         "marketId":"moneyline-1","marketType":"Moneyline","volume":"$12k",
         "selections":[{"name":"Yankees","price":"55 cents"}]}]}
    </script>
    """
    collector = FanaticsMarketsCollector(client=FakeClient(httpx.Response(200, text=html)))

    result = collector.collect(run_date="2026-09-15")

    assert len(result.snapshots) == 1
    snapshot = result.snapshots[0]
    assert snapshot.event.home_team.display_name == "New York Yankees"
    assert snapshot.prediction_markets[0].market_type == "Moneyline"
    assert snapshot.prediction_markets[0].displayed_price == "55 cents"
    assert "official_odds" in snapshot.missing_fields


def test_collects_nextjs_server_component_event_and_probability() -> None:
    payload = json.dumps({
        "id": "mlb-1", "series": "MLB", "startTime": 1789585200000,
        "status": "UPCOMING", "matchupProps": {
            "sideA": {"name": "Chicago White Sox"}, "sideB": {"name": "Cleveland Guardians"},
        },
        "markets": {"moneyline": [{"marketId": "m-1", "title": "Chicago White Sox", "probability": 0.42, "totalVolume": "1200"}]},
    })
    html = f"<script>self.__next_f.push([1,{json.dumps(payload)}])</script>"
    collector = FanaticsMarketsCollector(client=FakeClient(httpx.Response(200, text=html)))

    result = collector.collect(run_date="2026-09-16")

    assert result.snapshots[0].event.sport == "baseball"
    assert result.snapshots[0].prediction_markets[0].displayed_price == "42%"


def test_normalizes_known_soccer_leagues_to_the_catalog_sport_key() -> None:
    html = """
    <script type="application/json">
      {"eventId":"mls-1","series":"MLS","homeTeam":"Austin FC","awayTeam":"LA Galaxy",
       "startTime":"2026-09-15T19:00:00Z"}
    </script>
    """
    collector = FanaticsMarketsCollector(client=FakeClient(httpx.Response(200, text=html)))

    result = collector.collect(run_date="2026-09-15")

    assert result.snapshots[0].event.sport == "soccer"


@pytest.mark.parametrize("status", [403, 429])
def test_rejects_access_limited_pages(status: int) -> None:
    collector = FanaticsMarketsCollector(client=FakeClient(httpx.Response(status)))

    with pytest.raises(FanaticsMarketsError, match="rejected collection"):
        collector.collect(run_date="2026-09-15")
