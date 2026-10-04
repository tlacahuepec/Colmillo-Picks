"""Unit tests for TheOddsApiAdapter catalog odds provider."""

import httpx

from services.catalog.providers import (
    CatalogProvider,
    ProviderErrorCategory,
    ProviderRequest,
    ProviderStatus,
)
from services.catalog.odds_provider import (
    TheOddsApiAdapter,
    TheOddsApiConfig,
    normalize_odds_api_event,
)


def test_implements_catalog_provider_protocol():
    adapter = TheOddsApiAdapter()
    assert isinstance(adapter, CatalogProvider)
    assert adapter.provider_name == "the_odds_api"


def test_deterministic_replay_mlb():
    adapter = TheOddsApiAdapter(TheOddsApiConfig(api_key=None))
    req = ProviderRequest(
        sport="baseball",
        resource="odds",
        requested_at="2025-05-24T12:00:00Z",
        parameters={"home_team": "New York Yankees", "away_team": "Boston Red Sox"},
    )
    result = adapter.fetch(req)
    assert result.status == ProviderStatus.AVAILABLE
    assert result.quota_units == 0
    assert result.facts["home_team"] == "New York Yankees"
    assert result.facts["away_team"] == "Boston Red Sox"
    assert "moneyline" in result.facts["game_lines"]
    assert result.facts["game_lines"]["moneyline"]["home"] == -150

    props = result.facts["player_props"]
    assert len(props) > 0
    # Check Aaron Judge props
    judge_props = {p["market"]: p["line"] for p in props if p["player_name"] == "Aaron Judge"}
    assert judge_props.get("hits") == 1.5
    assert judge_props.get("home_runs") == 0.5
    assert judge_props.get("total_bases") == 2.5

    # Check Gerrit Cole pitcher prop
    cole_props = {p["market"]: p["line"] for p in props if p["player_name"] == "Gerrit Cole"}
    assert cole_props.get("strikeouts") == 7.5


def test_deterministic_replay_nba():
    adapter = TheOddsApiAdapter(TheOddsApiConfig(api_key=None))
    req = ProviderRequest(
        sport="basketball",
        resource="odds",
        requested_at="2025-06-05T12:00:00Z",
        parameters={"home_team": "Oklahoma City Thunder", "away_team": "Indiana Pacers"},
    )
    result = adapter.fetch(req)
    assert result.status == ProviderStatus.AVAILABLE
    assert result.facts["home_team"] == "Oklahoma City Thunder"
    assert result.facts["away_team"] == "Indiana Pacers"

    props = result.facts["player_props"]
    assert len(props) > 0

    sga_props = {p["market"]: p["line"] for p in props if p["player_name"] == "Shai Gilgeous-Alexander"}
    assert sga_props.get("points") == 30.5
    assert sga_props.get("rebounds") == 5.5
    assert sga_props.get("assists") == 6.5

    hali_props = {p["market"]: p["line"] for p in props if p["player_name"] == "Tyrese Haliburton"}
    assert hali_props.get("points") == 18.5
    assert hali_props.get("assists") == 9.5
    assert hali_props.get("threes") == 2.5


def test_deterministic_replay_unknown_players_in_parameters():
    adapter = TheOddsApiAdapter(TheOddsApiConfig(api_key=None))
    req = ProviderRequest(
        sport="baseball",
        resource="odds",
        requested_at="2025-05-24T12:00:00Z",
        parameters={
            "home_team": "New York Yankees",
            "away_team": "Boston Red Sox",
            "players": "Anthony Rizzo, Juan Soto",
        },
    )
    result = adapter.fetch(req)
    props = result.facts["player_props"]
    rizzo_props = [p for p in props if p["player_name"] == "Anthony Rizzo"]
    assert len(rizzo_props) > 0
    assert any(p["market"] == "hits" for p in rizzo_props)


def test_live_http_success_with_quota_headers():
    mock_response_payload = {
        "id": "live_game_123",
        "sport_key": "baseball_mlb",
        "home_team": "Los Angeles Dodgers",
        "away_team": "San Diego Padres",
        "commence_time": "2025-06-10T02:10:00Z",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Los Angeles Dodgers", "price": -165},
                            {"name": "San Diego Padres", "price": 140},
                        ],
                    },
                    {
                        "key": "batter_hits",
                        "outcomes": [
                            {"name": "Over", "description": "Shohei Ohtani", "price": -175, "point": 1.5},
                            {"name": "Under", "description": "Shohei Ohtani", "price": 135, "point": 1.5},
                        ],
                    },
                ],
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=mock_response_payload,
            headers={"x-requests-remaining": "480", "x-requests-used": "20"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = TheOddsApiAdapter(
        TheOddsApiConfig(api_key="test_live_key"),
        client=client,
    )
    req = ProviderRequest(
        sport="baseball",
        resource="odds",
        requested_at="2025-06-10T00:00:00Z",
        parameters={"home_team": "Los Angeles Dodgers", "away_team": "San Diego Padres"},
    )
    result = adapter.fetch(req)

    assert result.status == ProviderStatus.AVAILABLE
    assert result.quota_units == 1
    assert adapter.remaining_requests == 480
    assert adapter.used_requests == 20
    assert result.facts["home_team"] == "Los Angeles Dodgers"
    props = result.facts["player_props"]
    assert len(props) == 1
    assert props[0]["player_name"] == "Shohei Ohtani"
    assert props[0]["market"] == "hits"
    assert props[0]["line"] == 1.5
    assert props[0]["over_odds"] == -175


def test_live_http_auth_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Invalid API key"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = TheOddsApiAdapter(
        TheOddsApiConfig(api_key="bad_key"),
        client=client,
    )
    req = ProviderRequest(sport="baseball", resource="odds", requested_at="2025-06-10T00:00:00Z")
    result = adapter.fetch(req)

    assert result.status == ProviderStatus.UNAVAILABLE
    assert result.error_category == ProviderErrorCategory.AUTHENTICATION
    assert result.retryable is False


def test_live_http_rate_limited():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "Rate limit exceeded"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = TheOddsApiAdapter(
        TheOddsApiConfig(api_key="rate_limited_key"),
        client=client,
    )
    req = ProviderRequest(sport="baseball", resource="odds", requested_at="2025-06-10T00:00:00Z")
    result = adapter.fetch(req)

    assert result.status == ProviderStatus.UNAVAILABLE
    assert result.error_category == ProviderErrorCategory.RATE_LIMITED
    assert result.retryable is True


def test_live_http_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Connection timed out")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = TheOddsApiAdapter(
        TheOddsApiConfig(api_key="some_key"),
        client=client,
    )
    req = ProviderRequest(sport="baseball", resource="odds", requested_at="2025-06-10T00:00:00Z")
    result = adapter.fetch(req)

    assert result.status == ProviderStatus.UNAVAILABLE
    assert result.error_category == ProviderErrorCategory.TIMEOUT
    assert result.retryable is True


def test_normalize_odds_api_event_bookmaker_dedup():
    raw_event = {
        "id": "event_1",
        "sport_key": "basketball_nba",
        "home_team": "Boston Celtics",
        "away_team": "Los Angeles Lakers",
        "commence_time": "2025-05-20T20:00:00Z",
        "bookmakers": [
            {
                "key": "betmgm",
                "title": "BetMGM",
                "markets": [
                    {
                        "key": "player_points",
                        "outcomes": [
                            {"name": "Over", "description": "Jayson Tatum", "price": -120, "point": 26.5},
                        ],
                    }
                ],
            },
            {
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [
                    {
                        "key": "player_points",
                        "outcomes": [
                            {"name": "Over", "description": "Jayson Tatum", "price": -115, "point": 27.5},
                        ],
                    }
                ],
            },
        ],
    }

    # DraftKings has higher preference than BetMGM by default
    facts = normalize_odds_api_event(raw_event, "basketball", bookmaker_preference=("draftkings", "betmgm"))
    props = facts["player_props"]
    assert len(props) == 1
    assert props[0]["player_name"] == "Jayson Tatum"
    assert props[0]["line"] == 27.5
    assert props[0]["bookmaker"] == "DraftKings"
