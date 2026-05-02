from __future__ import annotations

import json

import pytest

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
                            "status": {"long": "Not Started", "short": "NS", "elapsed": None},
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
    assert fixture["status"] == {"long": "Not Started", "short": "NS"}
    assert len(call_urls) == 3
    assert "opponent" not in call_urls[-1]


def test_lookup_fixture_raises_sanitized_error_when_api_returns_errors() -> None:
    module = load_script_module("api_football_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    def fake_urlopen(request, timeout=0):
        return _FakeResponse({"errors": {"league": "bad league id"}, "response": []})

    provider = module.ApiFootballFixtureProvider(api_key="secret", urlopen_fn=fake_urlopen)

    with pytest.raises(module.ApiFootballProviderError, match="API-Football returned errors for /teams: league: bad league id"):
        provider.lookup_fixture(
            collector.MatchInputRequest(home_team="A", away_team="B", match_date="2026-05-01")
        )


def test_lookup_fixture_uses_league_and_season_hints_without_unsupported_opponent_param() -> None:
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
                        "fixture": {"id": 222, "date": "2026-05-01T19:00:00+00:00", "venue": {}},
                        "league": {"name": "Premier League", "type": "League", "country": "England"},
                        "teams": {
                            "home": {"id": 33, "name": "Manchester United"},
                            "away": {"id": 40, "name": "Liverpool"},
                        },
                    }
                ]
            }
        )

    provider = module.ApiFootballFixtureProvider(api_key="secret", urlopen_fn=fake_urlopen)

    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Manchester United",
            away_team="Liverpool",
            match_date="2026-05-01",
            competition="Premier League",
            league_id="39",
            season="2025",
        )
    )

    assert fixture is not None
    assert fixture["match_id"] == "222"
    assert "league=39" in call_urls[-1]
    assert "season=2025" in call_urls[-1]
    assert "date=2026-05-01" in call_urls[-1]
    assert "opponent" not in call_urls[-1]


def test_lookup_fixture_accepts_reversed_orientation_and_maps_api_home_away() -> None:
    module = load_script_module("api_football_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    def fake_urlopen(request, timeout=0):
        if "teams" in request.full_url:
            return _FakeResponse(
                {
                    "response": [
                        {"team": {"id": 42, "name": "Arsenal"}},
                        {"team": {"id": 40, "name": "Liverpool"}},
                    ]
                }
            )
        return _FakeResponse(
            {
                "response": [
                    {
                        "fixture": {"id": 456, "date": "2026-05-01T19:00:00+00:00", "venue": {}},
                        "league": {"name": "Premier League", "type": "League", "country": "England"},
                        "teams": {
                            "home": {"id": 40, "name": "Liverpool"},
                            "away": {"id": 42, "name": "Arsenal"},
                        },
                    }
                ]
            }
        )

    provider = module.ApiFootballFixtureProvider(api_key="secret", urlopen_fn=fake_urlopen)
    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(home_team="Arsenal", away_team="Liverpool", match_date="2026-05-01")
    )

    assert fixture is not None
    assert fixture["teams"]["home"]["team_name"] == "Liverpool"
    assert fixture["teams"]["away"]["team_name"] == "Arsenal"


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


def test_lookup_fixture_maps_partial_api_payload_with_safe_defaults() -> None:
    module = load_script_module("api_football_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    def fake_urlopen(request, timeout=0):
        if "teams" in request.full_url:
            return _FakeResponse({"response": [{"team": {"id": 9, "name": "Juve"}}]})
        return _FakeResponse(
            {
                "response": [
                    {
                        "fixture": {
                            "id": 321,
                            "date": "2026-05-01T19:00:00+00:00",
                            "venue": {},
                        },
                        "league": {"name": "", "type": "", "country": ""},
                        "teams": {"home": {}, "away": {}},
                    }
                ]
            }
        )

    provider = module.ApiFootballFixtureProvider(api_key="secret", urlopen_fn=fake_urlopen)
    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Juve",
            away_team="Milan",
            match_date="2026-05-01",
            competition="Serie A",
        )
    )

    assert fixture is not None
    assert fixture["competition"] == "Serie A"
    assert fixture["competition_type"] == "league"
    assert fixture["venue"] == {"name": "Unknown Venue", "city": "Unknown", "country": "Unknown"}
    assert fixture["teams"]["home"]["team_id"] == "9"
    assert fixture["teams"]["away"]["team_name"] == "Juve"


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


def test_get_odds_snapshots_skips_malformed_odds_and_uses_non_over_fallback_value() -> None:
    module = load_script_module("api_football_provider.py")

    def fake_urlopen(request, timeout=0):
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
                                            {"value": "Player A - Over 1.5", "odd": "N/A"},
                                            {"value": "Player A - Under 1.5", "odd": "2.02"},
                                        ],
                                    }
                                ],
                            },
                            {
                                "name": "Book Two",
                                "bets": [{"name": "Shots On Goal - Player", "values": [{"value": "missing", "odd": None}]}],
                            },
                        ]
                    }
                ]
            }
        )

    provider = module.ApiFootballOddsSnapshotProvider(api_key="secret", urlopen_fn=fake_urlopen)
    market_payload = provider.get_odds_snapshots({"match_id": "12345"})

    assert market_payload is not None
    assert [snap["source"] for snap in market_payload["sportsbook_snapshots"]] == ["Book One"]
    assert [snap["odds_decimal"] for snap in market_payload["sportsbook_snapshots"]] == [2.02]
    assert market_payload["sportsbook_snapshots"][0]["captured_at_utc"]


def test_api_football_providers_raise_clear_error_when_credentials_missing() -> None:
    module = load_script_module("api_football_provider.py")

    with pytest.raises(ValueError, match="Missing credentials for provider 'api-football'\\. Set API_FOOTBALL_API_KEY\\."):
        module.ApiFootballFixtureProvider(api_key=None)

    with pytest.raises(ValueError, match="Missing credentials for provider 'api-football'\\. Set API_FOOTBALL_API_KEY\\."):
        module.ApiFootballOddsSnapshotProvider(api_key=None)
