"""Deterministic payload assembly helpers for collect_match_inputs."""

from __future__ import annotations

from typing import Any


def build_teams_payload(fixture: dict[str, Any], lineup_payload: dict[str, Any], lineup_ts: str) -> list[dict[str, Any]]:
    teams_payload: list[dict[str, Any]] = []
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
    return teams_payload


def build_payload(
    request: Any,
    fixture: dict[str, Any],
    teams_payload: list[dict[str, Any]],
    normalized_snapshots: list[dict[str, Any]],
    normalized_players: list[dict[str, Any]],
    weather: dict[str, Any],
    market_ts: str,
    validation: dict[str, Any],
    default_kickoff_utc: str,
) -> dict[str, Any]:
    return {
        "schema_version": "v1.1.0",
        "match_id": fixture.get("match_id"),
        "competition": fixture.get("competition", request.competition),
        "match": {
            "match_id": fixture.get("match_id"),
            "competition_type": fixture.get("competition_type", "league"),
            "is_elimination": bool(fixture.get("is_elimination", False)),
            "overtime_possible": bool(fixture.get("overtime_possible", False)),
            "kickoff_utc": fixture.get("kickoff_utc", default_kickoff_utc),
            "venue": fixture.get("venue", {"name": "Unknown Venue", "city": "Unknown", "country": "Unknown"}),
            "weather": weather,
        },
        "teams": teams_payload,
        "market": {
            "source_timestamp_utc": market_ts,
            "sportsbook_snapshots": normalized_snapshots,
        },
        "players": normalized_players,
        "validation": validation,
    }
