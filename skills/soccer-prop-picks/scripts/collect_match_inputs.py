#!/usr/bin/env python3
"""Collect structured soccer match inputs for downstream prop scoring."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class MatchInputRequest:
    home_team: str
    away_team: str
    match_date: str
    competition: str = "League"


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _team_id(team_name: str) -> str:
    alpha = "".join(ch for ch in team_name.upper() if ch.isalpha())
    if len(alpha) >= 3:
        return alpha[:3]
    return (alpha + "XXX")[:3]


def collect_inputs(request: MatchInputRequest) -> dict[str, Any]:
    """Return normalized schema-compatible match inputs.

    This deterministic payload is a placeholder for future real integrations.
    """
    ts = _utc_now_z()
    home_id = _team_id(request.home_team)
    away_id = _team_id(request.away_team)
    match_id = f"{request.competition.replace(' ', '-').upper()}-{home_id}-{away_id}-{request.match_date}"

    return {
        "schema_version": "v1.1.0",
        "match_id": match_id,
        "competition": request.competition,
        "match": {
            "match_id": match_id,
            "competition_type": "league",
            "is_elimination": False,
            "overtime_possible": False,
            "kickoff_utc": f"{request.match_date}T19:45:00Z",
            "venue": {"name": f"{request.home_team} Stadium", "city": "Unknown", "country": "Unknown"},
            "weather": {
                "summary": "Partly cloudy",
                "temperature_c": 18,
                "wind_kph": 10,
                "precipitation_probability": 0.2,
                "source_timestamp_utc": ts,
            },
        },
        "teams": [
            {
                "team_id": home_id,
                "team_name": request.home_team,
                "home_away": "home",
                "projected_lineup": {
                    "status": "confirmed",
                    "formation": "4-3-3",
                    "starters": [f"{request.home_team} Player 1", f"{request.home_team} Player 2"],
                    "source_timestamp_utc": ts,
                },
                "injuries": [],
                "suspensions": [],
                "team_win_probability": 0.48,
                "last_5_results": ["W", "D", "W", "L", "W"],
                "possession_profile": {"avg_possession_pct": 54, "style_tag": "high_possession"},
                "standings_context": {
                    "table_position": 4,
                    "points": 60,
                    "games_played": 32,
                    "motivation_tag": "europe_race",
                },
            },
            {
                "team_id": away_id,
                "team_name": request.away_team,
                "home_away": "away",
                "projected_lineup": {
                    "status": "confirmed",
                    "formation": "4-2-3-1",
                    "starters": [f"{request.away_team} Player 1", f"{request.away_team} Player 2"],
                    "source_timestamp_utc": ts,
                },
                "injuries": [],
                "suspensions": [],
                "team_win_probability": 0.29,
                "last_5_results": ["W", "W", "D", "L", "D"],
                "possession_profile": {"avg_possession_pct": 50, "style_tag": "balanced"},
                "standings_context": {
                    "table_position": 7,
                    "points": 52,
                    "games_played": 32,
                    "motivation_tag": "midtable",
                },
            },
        ],
        "market": {
            "source_timestamp_utc": ts,
            "sportsbook_snapshots": [
                {"source": "book1", "odds_decimal": 1.85},
                {"source": "book2", "odds_decimal": 1.87},
                {"source": "book3", "odds_decimal": 1.84},
                {"source": "book4", "odds_decimal": 1.88},
                {"source": "book5", "odds_decimal": 1.86},
            ],
        },
        "players": [
            {
                "player_id": f"{home_id.lower()}-8",
                "player_name": f"{request.home_team} CM",
                "team_id": home_id,
                "position_group": "MID",
                "specific_role": "CM",
                "role_tag": "CM",
                "expected_minutes": 88,
                "substitution_risk": "low",
                "captain": True,
                "is_lone_striker": False,
                "expected_passes_baseline": 64,
                "expected_shots_baseline": 1.3,
                "market_lines": {"passes": 58.5, "shots": 1.5},
            },
            {
                "player_id": f"{home_id.lower()}-9",
                "player_name": f"{request.home_team} ST",
                "team_id": home_id,
                "position_group": "FWD",
                "specific_role": "ST",
                "role_tag": "ST",
                "expected_minutes": 86,
                "substitution_risk": "medium",
                "is_lone_striker": True,
                "expected_passes_baseline": 24,
                "expected_shots_baseline": 3.4,
                "market_lines": {"passes": 22.5, "shots": 2.5},
            },
            {
                "player_id": f"{away_id.lower()}-4",
                "player_name": f"{request.away_team} CB",
                "team_id": away_id,
                "position_group": "DEF",
                "specific_role": "CB",
                "role_tag": "CB",
                "expected_minutes": 90,
                "substitution_risk": "low",
                "is_lone_striker": False,
                "expected_passes_baseline": 68,
                "expected_shots_baseline": 0.4,
                "market_lines": {"passes": 61.5, "shots": 0.5},
            },
        ],
        "validation": {"critical_missing_fields": [], "should_reject_prediction": False},
    }


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
