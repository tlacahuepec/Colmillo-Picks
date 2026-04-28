from __future__ import annotations

import json

from tests.conftest import load_script_module


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_lookup_fixture_maps_api_football_payload_into_fixture_shape() -> None:
    module = load_script_module("api_football_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    call_urls: list[str] = []

    def fake_urlopen(request, timeout=0):
        call_urls.append(request.full_url)
        if "teams" in request.full_url:
            return _FakeResponse(
                {
                    "response": [
                        {"team": {"id": 33, "name": "Manchester United"}},
                        {"team": {"id": 40, "name": "Liverpool"}},
                    ]
                }
            )
        return _FakeResponse(
            {
                "response": [
                    {
                        "fixture": {
                            "id": 12345,
                            "date": "2026-05-01T19:00:00+00:00",
                            "venue": {"name": "Old Trafford", "city": "Manchester"},
                        },
                        "league": {"name": "Premier League", "type": "League", "country": "England"},
                        "teams": {
                            "home": {"id": 33, "name": "Manchester United"},
                            "away": {"id": 40, "name": "Liverpool"},
                        },
                    }
                ]
            }
        )

    provider = module.ApiFootballFixtureProvider(
        api_key="secret",
        urlopen_fn=fake_urlopen,
        timeout_seconds=2,
    )

    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Manchester United",
            away_team="Liverpool",
            match_date="2026-05-01",
            competition="Premier League",
        )
    )

    assert fixture is not None
    assert fixture["match_id"] == "12345"
    assert fixture["kickoff_utc"] == "2026-05-01T19:00:00Z"
    assert fixture["competition"] == "Premier League"
    assert fixture["competition_type"] == "league"
    assert fixture["teams"]["home"]["team_id"] == "33"
    assert fixture["teams"]["away"]["team_name"] == "Liverpool"
    assert fixture["venue"] == {"name": "Old Trafford", "city": "Manchester", "country": "England"}
    assert len(call_urls) == 3


def test_lookup_fixture_returns_none_when_fixture_not_found() -> None:
    module = load_script_module("api_football_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    def fake_urlopen(request, timeout=0):
        if "fixtures" in request.full_url:
            return _FakeResponse({"response": []})
        return _FakeResponse({"response": [{"team": {"id": 1, "name": "A"}}]})

    provider = module.ApiFootballFixtureProvider(api_key="secret", urlopen_fn=fake_urlopen)

    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(home_team="A", away_team="B", match_date="2026-05-01")
    )

    assert fixture is None


def test_get_odds_snapshots_maps_api_football_player_prop_odds() -> None:
    module = load_script_module("api_football_provider.py")

    call_urls: list[str] = []

    def fake_urlopen(request, timeout=0):
        call_urls.append(request.full_url)
        return _FakeResponse(
            {
                "response": [
                    {
                        "bookmakers": [
                            {
                                "name": "Book One",
                                "bets": [
                                    {
                                        "name": "Shots On Goal - Player",
                                        "values": [
                                            {"value": "Player A - Over 1.5", "odd": "1.83"},
                                            {"value": "Player A - Under 1.5", "odd": "1.95"},
                                        ],
                                    }
                                ],
                            },
                            {
                                "name": "Book Two",
                                "bets": [
                                    {
                                        "name": "Shots On Goal - Player",
                                        "values": [{"value": "Player A - Over 1.5", "odd": "1.88"}],
                                    }
                                ],
                            },
                        ]
                    }
                ]
            }
        )

    provider = module.ApiFootballOddsSnapshotProvider(
        api_key="secret",
        urlopen_fn=fake_urlopen,
        timeout_seconds=2,
    )

    market_payload = provider.get_odds_snapshots({"match_id": "12345"})

    assert market_payload is not None
    assert market_payload["source_timestamp_utc"]
    assert [snap["source"] for snap in market_payload["sportsbook_snapshots"]] == ["Book One", "Book Two"]
    assert [snap["odds_decimal"] for snap in market_payload["sportsbook_snapshots"]] == [1.83, 1.88]
    assert all(snap["captured_at_utc"] for snap in market_payload["sportsbook_snapshots"])
    assert "odds?fixture=12345" in call_urls[0]


def test_get_odds_snapshots_returns_empty_snapshots_when_api_has_no_markets() -> None:
    module = load_script_module("api_football_provider.py")

    def fake_urlopen(request, timeout=0):
        return _FakeResponse({"response": []})

    provider = module.ApiFootballOddsSnapshotProvider(api_key="secret", urlopen_fn=fake_urlopen)

    market_payload = provider.get_odds_snapshots({"match_id": "12345"})

    assert market_payload is not None
    assert market_payload["sportsbook_snapshots"] == []
