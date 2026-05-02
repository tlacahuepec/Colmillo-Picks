from __future__ import annotations

import pytest

from tests.conftest import load_script_module
from tests.test_input_schema_contract import _validate_payload


class _MissingFixtureProvider:
    def lookup_fixture(self, request):
        return None


class _SparseLineupProvider:
    def get_lineups_and_availability(self, fixture):
        return {
            "teams": {
                "home": {"status": "unknown", "formation": "unknown", "starters": []},
                "away": {"status": "unknown", "formation": "unknown", "starters": []},
            },
            "players": [],
        }


class _SparseOddsProvider:
    def get_odds_snapshots(self, fixture):
        return {"sportsbook_snapshots": [{"source": "book1", "odds_decimal": 1.9}]}


class _MissingWeatherProvider:
    def get_weather(self, fixture):
        return None


class _NoneLineupProvider:
    def get_lineups_and_availability(self, fixture):
        return None


class _MissingTimestampsProviders:
    def get_lineups_and_availability(self, fixture):
        return {
            "teams": {
                "home": {"status": "projected", "formation": "4-3-3", "starters": []},
                "away": {"status": "projected", "formation": "4-4-2", "starters": []},
            },
            "players": [
                {
                    "player_id": "h-1",
                    "player_name": "Home Mid",
                    "team_id": fixture["teams"]["home"]["team_id"],
                    "role_tag": "CM",
                }
            ],
        }

    def get_odds_snapshots(self, fixture):
        return {
            "sportsbook_snapshots": [
                {
                    "source": "solo-book",
                    "odds_decimal": 2.01,
                }
            ]
        }


class _EmptyPlayersProvider:
    def get_lineups_and_availability(self, fixture):
        return {
            "source_timestamp_utc": "2026-05-03T08:00:00Z",
            "teams": {
                "home": {"status": "unknown", "formation": "unknown", "starters": []},
                "away": {"status": "unknown", "formation": "unknown", "starters": []},
            },
            "players": [],
        }


def test_collect_inputs_produces_schema_compatible_complete_payload() -> None:
    collector = load_script_module("collect_match_inputs.py")

    payload = collector.collect_inputs(
        collector.MatchInputRequest(
            home_team="Arsenal",
            away_team="Liverpool",
            match_date="2026-05-03",
            competition="Premier League",
        )
    )

    assert _validate_payload(payload) == []
    assert payload["validation"]["critical_missing_fields"] == []
    assert payload["validation"]["should_reject_prediction"] is False
    assert payload.keys() >= {"schema_version", "match", "teams", "market", "players", "validation"}
    assert payload["market"]["source_timestamp_utc"]
    assert len(payload["market"]["sportsbook_snapshots"]) >= 2
    assert all("captured_at_utc" in snap for snap in payload["market"]["sportsbook_snapshots"])


def test_collect_inputs_fallbacks_are_transparent_and_flagged() -> None:
    collector = load_script_module("collect_match_inputs.py")

    payload = collector.collect_inputs(
        collector.MatchInputRequest(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
        fixture_provider=_MissingFixtureProvider(),
        lineup_provider=_SparseLineupProvider(),
        odds_provider=_SparseOddsProvider(),
        weather_provider=_MissingWeatherProvider(),
    )

    assert _validate_payload(payload) == []
    assert "match" in payload["validation"]["critical_missing_fields"]
    assert "market.sportsbook_snapshots" in payload["validation"]["critical_missing_fields"]
    assert "players" in payload["validation"]["critical_missing_fields"]
    assert payload["validation"]["should_reject_prediction"] is True
    assert "fallback" in payload["validation"]["notes"].lower()
    assert payload["validation"]["provider_status"]["fixture"]["fallback_used"] is True
    assert payload["validation"]["provider_status"]["weather"]["success"] is False


def test_collect_inputs_rejects_missing_fixture_when_fallback_disabled() -> None:
    collector = load_script_module("collect_match_inputs.py")

    with pytest.raises(Exception, match="Fixture lookup failed: No API-Football fixture matched Juve vs Milan on 2026-05-03\\."):
        collector.collect_inputs(
            collector.MatchInputRequest(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
            fixture_provider=_MissingFixtureProvider(),
            allow_fixture_fallback=False,
        )


def test_collect_inputs_preserves_fixture_status_in_match_payload() -> None:
    collector = load_script_module("collect_match_inputs.py")

    class _StatusFixtureProvider:
        def lookup_fixture(self, request):
            fixture = collector.DeterministicFixtureProvider().lookup_fixture(request)
            fixture["status"] = {"long": "Not Started", "short": "NS", "elapsed": 0}
            return fixture

    payload = collector.collect_inputs(
        collector.MatchInputRequest(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
        fixture_provider=_StatusFixtureProvider(),
    )

    assert _validate_payload(payload) == []
    assert payload["match"]["status"] == {"long": "Not Started", "short": "NS", "elapsed": 0}


def test_collect_inputs_prefers_parsed_fields_and_competition_hints() -> None:
    collector = load_script_module("collect_match_inputs.py")

    payload = collector.collect_inputs(
        collector.MatchInputRequest(
            home_team="raw home",
            away_team="raw away",
            match_date="2026-05-03",
            competition="League",
            parsed_home_team="Real Madrid",
            parsed_away_team="Barcelona",
            parsed_match_date="2026-05-04",
            competition_hints=["La Liga", "Spain"],
        )
    )

    assert payload["competition"] == "La Liga"
    assert payload["teams"][0]["team_name"] == "Real Madrid"
    assert payload["teams"][1]["team_name"] == "Barcelona"
    assert payload["match"]["kickoff_utc"].startswith("2026-05-04")


def test_collect_inputs_date_parse_failure_raises_explicit_error() -> None:
    collector = load_script_module("collect_match_inputs.py")

    with pytest.raises(ValueError, match="Match date must use YYYY-MM-DD format"):
        collector.collect_inputs(
            collector.MatchInputRequest(home_team="Juve", away_team="Milan", match_date="05/03/2026")
        )


def test_collect_inputs_sets_provider_missing_note_when_lineups_unavailable() -> None:
    collector = load_script_module("collect_match_inputs.py")

    payload = collector.collect_inputs(
        collector.MatchInputRequest(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
        lineup_provider=_NoneLineupProvider(),
    )

    assert payload["validation"]["should_reject_prediction"] is False
    assert "Lineup provider unavailable" in payload["validation"]["notes"]


def test_collect_inputs_characterizes_timestamp_defaults_when_missing() -> None:
    collector = load_script_module("collect_match_inputs.py")
    providers = _MissingTimestampsProviders()

    payload = collector.collect_inputs(
        collector.MatchInputRequest(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
        lineup_provider=providers,
        odds_provider=providers,
    )

    assert payload["market"]["source_timestamp_utc"]
    assert payload["teams"][0]["projected_lineup"]["source_timestamp_utc"]
    assert "Lineup timestamp missing" in payload["validation"]["notes"]
    assert "Market timestamp missing" in payload["validation"]["notes"]


def test_collect_inputs_characterizes_snapshot_padding_to_schema_minimum() -> None:
    collector = load_script_module("collect_match_inputs.py")

    payload = collector.collect_inputs(
        collector.MatchInputRequest(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
        odds_provider=_SparseOddsProvider(),
    )

    assert len(payload["market"]["sportsbook_snapshots"]) == 2
    assert "market.sportsbook_snapshots" in payload["validation"]["critical_missing_fields"]


def test_collect_inputs_characterizes_rejection_when_players_missing() -> None:
    collector = load_script_module("collect_match_inputs.py")

    payload = collector.collect_inputs(
        collector.MatchInputRequest(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
        lineup_provider=_EmptyPlayersProvider(),
    )

    assert "players" in payload["validation"]["critical_missing_fields"]
    assert payload["validation"]["should_reject_prediction"] is True


def test_collect_inputs_uses_api_provider_by_default_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    collector = load_script_module("collect_match_inputs.py")

    called: dict[str, object] = {}

    class _Provider:
        api_key = "fake"

        def lookup_fixture(self, request):
            called["lookup"] = request.home_team
            return collector.DeterministicFixtureProvider().lookup_fixture(request)

    monkeypatch.setenv("API_FOOTBALL_API_KEY", "fake")
    monkeypatch.setattr(collector, "ApiFootballFixtureProvider", lambda *, config: _Provider())

    payload = collector.collect_inputs(
        collector.MatchInputRequest(home_team="Juve", away_team="Milan", match_date="2026-05-03")
    )

    assert called["lookup"] == "Juve"
    assert payload["match"]["match_id"]


def test_collect_inputs_uses_api_odds_provider_by_default_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    collector = load_script_module("collect_match_inputs.py")

    called: dict[str, object] = {}

    class _OddsProvider:
        api_key = "fake"

        def get_odds_snapshots(self, fixture):
            called["fixture"] = fixture["match_id"]
            ts = "2026-05-03T10:00:00Z"
            return {
                "source_timestamp_utc": ts,
                "sportsbook_snapshots": [
                    {"source": "api-book-1", "odds_decimal": 1.81, "captured_at_utc": ts},
                    {"source": "api-book-2", "odds_decimal": 1.84, "captured_at_utc": ts},
                ],
            }

    monkeypatch.setenv("API_FOOTBALL_API_KEY", "fake")
    monkeypatch.setattr(collector, "ApiFootballOddsSnapshotProvider", lambda *, config: _OddsProvider())

    payload = collector.collect_inputs(
        collector.MatchInputRequest(home_team="Juve", away_team="Milan", match_date="2026-05-03")
    )

    assert called["fixture"] == payload["match"]["match_id"]
    assert [snap["source"] for snap in payload["market"]["sportsbook_snapshots"][:2]] == ["api-book-1", "api-book-2"]


def test_collect_inputs_includes_provider_status_map() -> None:
    collector = load_script_module("collect_match_inputs.py")

    payload = collector.collect_inputs(
        collector.MatchInputRequest(home_team="Arsenal", away_team="Liverpool", match_date="2026-05-03")
    )

    provider_status = payload["validation"]["provider_status"]
    assert set(provider_status) == {"fixture", "lineup", "odds", "weather"}
    for provider in provider_status.values():
        assert set(provider) == {"attempted", "success", "fallback_used", "error_summary"}
