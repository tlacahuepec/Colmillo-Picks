#!/usr/bin/env python3
"""Collect structured soccer match inputs for downstream prop scoring."""

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


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


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _team_id(team_name: str) -> str:
    alpha = "".join(ch for ch in team_name.upper() if ch.isalpha())
    if len(alpha) >= 3:
        return alpha[:3]
    return (alpha + "XXX")[:3]


def _normalize_team_name(team_name: str) -> str:
    tokens = [token for token in team_name.strip().split() if token]
    return " ".join(token.capitalize() for token in tokens) if tokens else team_name.strip()


def _normalize_match_date(match_date: str) -> str:
    return datetime.strptime(match_date.strip(), "%Y-%m-%d").date().isoformat()


def _deterministic_last5(seed: str) -> list[str]:
    vals = ["W", "D", "L"]
    return [vals[(sum(ord(c) for c in f"{seed}-{idx}") + idx) % 3] for idx in range(5)]


def _derive_position_group(role_tag: str) -> str:
    if role_tag in {"GK"}:
        return "GK"
    if role_tag in {"CB", "LB", "RB", "LWB", "RWB"}:
        return "DEF"
    if role_tag in {"CM", "CDM", "CAM", "LM", "RM", "DM"}:
        return "MID"
    return "FWD"


class DeterministicFixtureProvider:
    def lookup_fixture(self, request: MatchInputRequest) -> dict[str, Any]:
        home = _normalize_team_name(request.parsed_home_team or request.home_team)
        away = _normalize_team_name(request.parsed_away_team or request.away_team)
        date = _normalize_match_date(request.parsed_match_date or request.match_date)
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


def collect_inputs(
    request: MatchInputRequest,
    fixture_provider: FixtureLookupProvider | None = None,
    lineup_provider: LineupAvailabilityProvider | None = None,
    odds_provider: OddsSnapshotProvider | None = None,
    weather_provider: WeatherProvider | None = None,
) -> dict[str, Any]:
    """Return normalized schema-compatible match inputs with transparent fallbacks."""
    fixture_provider = fixture_provider or DeterministicFixtureProvider()
    lineup_provider = lineup_provider or DeterministicLineupProvider()
    odds_provider = odds_provider or DeterministicOddsProvider()
    weather_provider = weather_provider or DeterministicWeatherProvider()

    critical_missing_fields: list[str] = []
    notes: list[str] = []

    fixture = fixture_provider.lookup_fixture(request)
    if not fixture:
        critical_missing_fields.append("match")
        notes.append("Fixture provider unavailable; used deterministic fallback fixture metadata.")
        fixture = _default_fixture_from_request(request)

    lineup_payload = lineup_provider.get_lineups_and_availability(fixture)
    if not lineup_payload:
        critical_missing_fields.append("teams.projected_lineup")
        notes.append("Lineup provider unavailable; used deterministic projected lineups and players.")
        lineup_payload = DeterministicLineupProvider().get_lineups_and_availability(fixture)

    market_payload = odds_provider.get_odds_snapshots(fixture)
    if not market_payload:
        critical_missing_fields.append("market.sportsbook_snapshots")
        notes.append("Odds provider unavailable; used deterministic synthetic odds snapshots.")
        market_payload = DeterministicOddsProvider().get_odds_snapshots(fixture)

    weather_payload = weather_provider.get_weather(fixture)
    if not weather_payload:
        critical_missing_fields.append("match.weather")
        notes.append("Weather provider unavailable; used neutral weather assumptions.")
        weather_payload = DeterministicWeatherProvider().get_weather(fixture)

    lineup_ts = lineup_payload.get("source_timestamp_utc") or _utc_now_z()
    if "source_timestamp_utc" not in lineup_payload:
        notes.append("Lineup timestamp missing in provider payload; populated with collection timestamp.")

    market_ts = market_payload.get("source_timestamp_utc") or _utc_now_z()
    if "source_timestamp_utc" not in market_payload:
        notes.append("Market timestamp missing in provider payload; populated with collection timestamp.")

    home_team = fixture["teams"]["home"]
    away_team = fixture["teams"]["away"]
    teams_payload = []
    for side, home_away in (("home", "home"), ("away", "away")):
        team_info = fixture["teams"][side]
        lineup_info = (lineup_payload.get("teams") or {}).get(side, {})
        teams_payload.append(
            {
                "team_id": team_info["team_id"],
                "team_name": team_info["team_name"],
                "home_away": home_away,
                "projected_lineup": {
                    "status": lineup_info.get("status", "unknown"),
                    "formation": lineup_info.get("formation", "unknown"),
                    "starters": lineup_info.get("starters", []),
                    "source_timestamp_utc": lineup_info.get("source_timestamp_utc", lineup_ts),
                },
                "injuries": lineup_info.get("injuries", []),
                "suspensions": lineup_info.get("suspensions", []),
                "team_win_probability": float(team_info.get("team_win_probability", 0.33)),
                "last_5_results": team_info.get("last_5_results", ["D", "D", "D", "D", "D"]),
                "possession_profile": team_info.get(
                    "possession_profile",
                    {"avg_possession_pct": 50, "style_tag": "balanced"},
                ),
                "standings_context": team_info.get(
                    "standings_context",
                    {
                        "table_position": 10,
                        "points": 40,
                        "games_played": 30,
                        "motivation_tag": "midtable",
                    },
                ),
            }
        )

    def _normalize_player(player: dict[str, Any]) -> dict[str, Any]:
        role = player.get("role_tag") or player.get("specific_role") or "CM"
        return {
            "player_id": player.get("player_id", "unknown-player"),
            "player_name": player.get("player_name", "Unknown Player"),
            "team_id": player.get("team_id", home_team["team_id"]),
            "position_group": player.get("position_group", _derive_position_group(role)),
            "specific_role": player.get("specific_role", role),
            "role_tag": role,
            "expected_minutes": int(player.get("expected_minutes", 75)),
            "substitution_risk": player.get("substitution_risk", "medium"),
            "captain": bool(player.get("captain", False)),
            "is_lone_striker": bool(player.get("is_lone_striker", False)),
            "expected_passes_baseline": float(player.get("expected_passes_baseline", 25)),
            "expected_shots_baseline": float(player.get("expected_shots_baseline", 1)),
            "market_lines": {
                "passes": float((player.get("market_lines") or {}).get("passes", 20.5)),
                "shots": float((player.get("market_lines") or {}).get("shots", 1.5)),
            },
        }

    players = lineup_payload.get("players") or []
    normalized_players: list[dict[str, Any]] = [_normalize_player(player) for player in players]

    if not normalized_players:
        critical_missing_fields.append("players")
        notes.append("No player-level provider data returned; used deterministic fallback players.")
        fallback_players = DeterministicLineupProvider().get_lineups_and_availability(fixture)["players"]
        normalized_players = [_normalize_player(player) for player in fallback_players]

    snapshots = market_payload.get("sportsbook_snapshots") or []
    normalized_snapshots = [
        {
            "source": snap.get("source", "unknown_book"),
            "odds_decimal": float(snap.get("odds_decimal", 2.0)),
            "captured_at_utc": snap.get("captured_at_utc", market_ts),
        }
        for snap in snapshots
    ]

    if len(normalized_snapshots) < 2:
        critical_missing_fields.append("market.sportsbook_snapshots")
        notes.append("Insufficient odds snapshots from provider; padded with deterministic fallback snapshots.")
        fallback_snaps = DeterministicOddsProvider().get_odds_snapshots(fixture)["sportsbook_snapshots"]
        normalized_snapshots = (normalized_snapshots + fallback_snaps)[:2]

    should_reject = any(
        field in {"match", "players", "market.sportsbook_snapshots"} for field in critical_missing_fields
    )

    payload = {
        "schema_version": "v1.1.0",
        "match_id": fixture.get("match_id"),
        "competition": fixture.get("competition", request.competition),
        "match": {
            "match_id": fixture.get("match_id"),
            "competition_type": fixture.get("competition_type", "league"),
            "is_elimination": bool(fixture.get("is_elimination", False)),
            "overtime_possible": bool(fixture.get("overtime_possible", False)),
            "kickoff_utc": fixture.get("kickoff_utc", f"{_normalize_match_date(request.match_date)}T19:45:00Z"),
            "venue": fixture.get(
                "venue", {"name": "Unknown Venue", "city": "Unknown", "country": "Unknown"}
            ),
            "weather": {
                "summary": weather_payload.get("summary", "Unknown"),
                "temperature_c": float(weather_payload.get("temperature_c", 15)),
                "wind_kph": float(weather_payload.get("wind_kph", 10)),
                "precipitation_probability": float(weather_payload.get("precipitation_probability", 0.2)),
                "source_timestamp_utc": weather_payload.get("source_timestamp_utc", _utc_now_z()),
            },
        },
        "teams": teams_payload,
        "market": {
            "source_timestamp_utc": market_ts,
            "sportsbook_snapshots": normalized_snapshots,
        },
        "players": normalized_players,
        "validation": {
            "critical_missing_fields": sorted(set(critical_missing_fields)),
            "should_reject_prediction": should_reject,
            "notes": " ".join(notes) if notes else "All required providers returned data.",
        },
    }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect soccer match inputs.")
    parser.add_argument("home_team", help="Home team name")
    parser.add_argument("away_team", help="Away team name")
    parser.add_argument("match_date", help="Match date in YYYY-MM-DD")
    parser.add_argument("--competition", default="League", help="Competition code/name")
    args = parser.parse_args()

    payload = collect_inputs(
        MatchInputRequest(
            home_team=args.home_team,
            away_team=args.away_team,
            match_date=args.match_date,
            competition=args.competition,
        )
    )
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
