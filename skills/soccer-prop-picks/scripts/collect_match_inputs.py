#!/usr/bin/env python3
"""Collect structured soccer match inputs for downstream prop scoring."""

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from api_football_provider import ApiFootballFixtureProvider, ApiFootballOddsSnapshotProvider
from normalizers import normalize_match_date, normalize_player, normalize_snapshots, normalize_team_name, normalize_weather
from provider_config import ApiFootballProviderConfig
from payload_builder import build_payload, build_teams_payload
from provider_resolution import (
    ResolutionContext,
    append_insufficient_snapshots,
    append_players_missing,
    build_validation,
    resolve_fixture,
    resolve_lineup,
    resolve_market,
    resolve_timestamp,
    resolve_weather,
)


class FixtureLookupProvider(Protocol):
    """Adapter contract for fixture lookup."""

    def lookup_fixture(self, request: "MatchInputRequest") -> dict[str, Any] | None:
        ...


class LineupAvailabilityProvider(Protocol):
    """Adapter contract for projected lineups, injuries, and player baselines."""

    def get_lineups_and_availability(self, fixture: dict[str, Any]) -> dict[str, Any] | None:
        ...


class OddsSnapshotProvider(Protocol):
    """Adapter contract for odds snapshots."""

    def get_odds_snapshots(self, fixture: dict[str, Any]) -> dict[str, Any] | None:
        ...


class WeatherProvider(Protocol):
    """Adapter contract for weather retrieval."""

    def get_weather(self, fixture: dict[str, Any]) -> dict[str, Any] | None:
        ...


@dataclass
class MatchInputRequest:
    home_team: str
    away_team: str
    match_date: str
    competition: str = "League"
    parsed_home_team: str | None = None
    parsed_away_team: str | None = None
    parsed_match_date: str | None = None
    competition_hints: list[str] | None = None
    league_id: str | None = None
    season: str | None = None


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _team_id(team_name: str) -> str:
    alpha = "".join(ch for ch in team_name.upper() if ch.isalpha())
    if len(alpha) >= 3:
        return alpha[:3]
    return (alpha + "XXX")[:3]


def _deterministic_last5(seed: str) -> list[str]:
    vals = ["W", "D", "L"]
    return [vals[(sum(ord(c) for c in f"{seed}-{idx}") + idx) % 3] for idx in range(5)]


class DeterministicFixtureProvider:
    def lookup_fixture(self, request: MatchInputRequest) -> dict[str, Any]:
        home = normalize_team_name(request.parsed_home_team or request.home_team)
        away = normalize_team_name(request.parsed_away_team or request.away_team)
        date = normalize_match_date(request.parsed_match_date or request.match_date)
        competition = (request.competition_hints or [request.competition])[0]
        home_id = _team_id(home)
        away_id = _team_id(away)
        match_id = f"{competition.replace(' ', '-').upper()}-{home_id}-{away_id}-{date}"

        return {
            "match_id": match_id,
            "competition": competition,
            "competition_type": "league",
            "is_elimination": False,
            "overtime_possible": False,
            "kickoff_utc": f"{date}T19:45:00Z",
            "venue": {
                "name": f"{home} Stadium",
                "city": "Unknown",
                "country": "Unknown",
            },
            "teams": {
                "home": {
                    "team_id": home_id,
                    "team_name": home,
                    "team_win_probability": 0.48,
                    "last_5_results": _deterministic_last5(home),
                    "possession_profile": {"avg_possession_pct": 54, "style_tag": "high_possession"},
                    "standings_context": {
                        "table_position": 4,
                        "points": 60,
                        "games_played": 32,
                        "motivation_tag": "europe_race",
                    },
                },
                "away": {
                    "team_id": away_id,
                    "team_name": away,
                    "team_win_probability": 0.29,
                    "last_5_results": _deterministic_last5(away),
                    "possession_profile": {"avg_possession_pct": 49, "style_tag": "balanced"},
                    "standings_context": {
                        "table_position": 8,
                        "points": 50,
                        "games_played": 32,
                        "motivation_tag": "midtable",
                    },
                },
            },
        }


class DeterministicLineupProvider:
    def get_lineups_and_availability(self, fixture: dict[str, Any]) -> dict[str, Any]:
        ts = _utc_now_z()
        home = fixture["teams"]["home"]
        away = fixture["teams"]["away"]

        return {
            "source_timestamp_utc": ts,
            "teams": {
                "home": {
                    "status": "projected",
                    "formation": "4-3-3",
                    "starters": [f"{home['team_name']} Starter {idx}" for idx in range(1, 12)],
                    "injuries": [],
                    "suspensions": [],
                },
                "away": {
                    "status": "projected",
                    "formation": "4-2-3-1",
                    "starters": [f"{away['team_name']} Starter {idx}" for idx in range(1, 12)],
                    "injuries": [],
                    "suspensions": [],
                },
            },
            "players": [
                {
                    "player_id": f"{home['team_id'].lower()}-8",
                    "player_name": f"{home['team_name']} CM",
                    "team_id": home["team_id"],
                    "role_tag": "CM",
                    "specific_role": "CM",
                    "expected_minutes": 88,
                    "substitution_risk": "low",
                    "captain": True,
                    "is_lone_striker": False,
                    "expected_passes_baseline": 64,
                    "expected_shots_baseline": 1.3,
                    "market_lines": {"passes": 58.5, "shots": 1.5},
                },
                {
                    "player_id": f"{home['team_id'].lower()}-9",
                    "player_name": f"{home['team_name']} ST",
                    "team_id": home["team_id"],
                    "role_tag": "ST",
                    "specific_role": "ST",
                    "expected_minutes": 86,
                    "substitution_risk": "medium",
                    "captain": False,
                    "is_lone_striker": True,
                    "expected_passes_baseline": 24,
                    "expected_shots_baseline": 3.4,
                    "market_lines": {"passes": 22.5, "shots": 2.5},
                },
                {
                    "player_id": f"{away['team_id'].lower()}-4",
                    "player_name": f"{away['team_name']} CB",
                    "team_id": away["team_id"],
                    "role_tag": "CB",
                    "specific_role": "CB",
                    "expected_minutes": 90,
                    "substitution_risk": "low",
                    "captain": False,
                    "is_lone_striker": False,
                    "expected_passes_baseline": 68,
                    "expected_shots_baseline": 0.4,
                    "market_lines": {"passes": 61.5, "shots": 0.5},
                },
            ],
        }


class DeterministicOddsProvider:
    def get_odds_snapshots(self, fixture: dict[str, Any]) -> dict[str, Any]:
        ts = _utc_now_z()
        return {
            "source_timestamp_utc": ts,
            "sportsbook_snapshots": [
                {"source": "book1", "odds_decimal": 1.85, "captured_at_utc": ts},
                {"source": "book2", "odds_decimal": 1.87, "captured_at_utc": ts},
                {"source": "book3", "odds_decimal": 1.84, "captured_at_utc": ts},
            ],
        }


class DeterministicWeatherProvider:
    def get_weather(self, fixture: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": "Partly cloudy",
            "temperature_c": 18,
            "wind_kph": 10,
            "precipitation_probability": 0.2,
            "source_timestamp_utc": _utc_now_z(),
        }


def _default_fixture_from_request(request: MatchInputRequest) -> dict[str, Any]:
    return DeterministicFixtureProvider().lookup_fixture(request)


def _default_fixture_provider() -> FixtureLookupProvider:
    config = ApiFootballProviderConfig.from_env()
    if not config.api_key:
        return DeterministicFixtureProvider()
    return ApiFootballFixtureProvider(config=config)


def _default_odds_provider() -> OddsSnapshotProvider:
    config = ApiFootballProviderConfig.from_env()
    if not config.api_key:
        return DeterministicOddsProvider()
    return ApiFootballOddsSnapshotProvider(config=config)


def collect_inputs(
    request: MatchInputRequest,
    fixture_provider: FixtureLookupProvider | None = None,
    lineup_provider: LineupAvailabilityProvider | None = None,
    odds_provider: OddsSnapshotProvider | None = None,
    weather_provider: WeatherProvider | None = None,
    allow_fixture_fallback: bool = True,
) -> dict[str, Any]:
    """Return normalized schema-compatible match inputs with transparent fallbacks."""
    fixture_provider = fixture_provider or _default_fixture_provider()
    lineup_provider = lineup_provider or DeterministicLineupProvider()
    odds_provider = odds_provider or _default_odds_provider()
    weather_provider = weather_provider or DeterministicWeatherProvider()

    fallback_lineup_provider = DeterministicLineupProvider()
    fallback_odds_provider = DeterministicOddsProvider()
    fallback_weather_provider = DeterministicWeatherProvider()

    context = ResolutionContext()
    fixture = resolve_fixture(
        request,
        fixture_provider,
        _default_fixture_from_request,
        context,
        allow_fallback=allow_fixture_fallback,
    )
    lineup_payload = resolve_lineup(fixture, lineup_provider, fallback_lineup_provider, context)
    market_payload = resolve_market(fixture, odds_provider, fallback_odds_provider, context)
    weather_payload = resolve_weather(fixture, weather_provider, fallback_weather_provider, context)

    lineup_ts = resolve_timestamp(
        lineup_payload,
        "source_timestamp_utc",
        "Lineup timestamp missing in provider payload; populated with collection timestamp.",
        _utc_now_z,
        context,
    )
    market_ts = resolve_timestamp(
        market_payload,
        "source_timestamp_utc",
        "Market timestamp missing in provider payload; populated with collection timestamp.",
        _utc_now_z,
        context,
    )

    home_team = fixture["teams"]["home"]
    teams_payload = build_teams_payload(fixture, lineup_payload, lineup_ts)

    players = lineup_payload.get("players") or []
    normalized_players: list[dict[str, Any]] = [normalize_player(player, home_team["team_id"]) for player in players]

    if not normalized_players:
        append_players_missing(context)
        fallback_players = fallback_lineup_provider.get_lineups_and_availability(fixture)["players"]
        normalized_players = [normalize_player(player, home_team["team_id"]) for player in fallback_players]

    snapshots = market_payload.get("sportsbook_snapshots") or []
    normalized_snapshots = normalize_snapshots(snapshots, market_ts)

    if len(normalized_snapshots) < 2:
        append_insufficient_snapshots(context)
        fallback_snaps = fallback_odds_provider.get_odds_snapshots(fixture)["sportsbook_snapshots"]
        normalized_snapshots = (normalized_snapshots + fallback_snaps)[:2]

    validation = build_validation(context)
    default_kickoff_utc = f"{normalize_match_date(request.match_date)}T19:45:00Z"
    weather = normalize_weather(weather_payload, _utc_now_z())

    return build_payload(
        request=request,
        fixture=fixture,
        teams_payload=teams_payload,
        normalized_snapshots=normalized_snapshots,
        normalized_players=normalized_players,
        weather=weather,
        market_ts=market_ts,
        validation=validation,
        default_kickoff_utc=default_kickoff_utc,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect soccer match inputs.")
    parser.add_argument("home_team", help="Home team name")
    parser.add_argument("away_team", help="Away team name")
    parser.add_argument("match_date", help="Match date in YYYY-MM-DD")
    parser.add_argument("--competition", default="League", help="Competition code/name")
    parser.add_argument("--league-id", default=None, help="API-Football league ID hint")
    parser.add_argument("--season", default=None, help="API-Football season hint")
    parser.add_argument(
        "--strict-fixture",
        action="store_true",
        help="Reject instead of using deterministic fallback when fixture lookup fails",
    )
    args = parser.parse_args()

    payload = collect_inputs(
        MatchInputRequest(
            home_team=args.home_team,
            away_team=args.away_team,
            match_date=args.match_date,
            competition=args.competition,
            competition_hints=[args.competition] if args.competition != "League" else None,
            league_id=args.league_id,
            season=args.season,
        ),
        allow_fixture_fallback=not args.strict_fixture,
    )
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
