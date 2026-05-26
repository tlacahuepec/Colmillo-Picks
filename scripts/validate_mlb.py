"""MLB validation harness CLI.

Runs the baseball scoring engine against a sample of historical games
and reports reproducibility and hit rate metrics.

Usage:
    python scripts/validate_mlb.py
    python scripts/validate_mlb.py --market strikeouts
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "soccer-prop-picks" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from baseball_scoring import score_baseball_props  # noqa: E402
from mlb_settlement import SettlementResult, grade_game_outcomes  # noqa: E402


_SAMPLE_GAMES: list[dict[str, Any]] = [
    {
        "game_id": "NYY-BOS-2026-05-20",
        "status": "final",
        "innings": 9,
        "players": [
            {
                "player_name": "Aaron Judge", "player_type": "batter", "team": "NYY",
                "batting_order": 2, "handedness": "R", "opposing_pitcher_hand": "L",
                "hits_per_game": 1.4, "hits_last5_per_game": 1.8,
                "hr_per_game": 0.35, "hr_last5_per_game": 0.6,
                "k_per_game": 1.8, "k_last5_per_game": 1.4,
                "park_factor": 0.55, "hr_factor": 0.6, "temp_f": 78,
                "wind_direction": "out to center", "team_implied_total": 5.2,
                "home_away": "home", "opp_k_rate": 0.22, "market_agreement": 0.7,
                "line_hits": 1.5, "line_home_runs": 0.5, "line_strikeouts": 1.5,
            },
        ],
        "actuals": {"Aaron Judge": {"hits": 2, "home_runs": 1, "strikeouts": 1}},
    },
    {
        "game_id": "LAD-SF-2026-05-20",
        "status": "final",
        "innings": 9,
        "players": [
            {
                "player_name": "Mookie Betts", "player_type": "batter", "team": "LAD",
                "batting_order": 1, "handedness": "R", "opposing_pitcher_hand": "R",
                "hits_per_game": 1.3, "hits_last5_per_game": 1.0,
                "hr_per_game": 0.2, "hr_last5_per_game": 0.2,
                "k_per_game": 1.2, "k_last5_per_game": 1.4,
                "park_factor": 0.48, "temp_f": 65, "wind_direction": "in",
                "team_implied_total": 4.5, "home_away": "away",
                "opp_k_rate": 0.25, "market_agreement": 0.5,
                "line_hits": 1.5, "line_home_runs": 0.5, "line_strikeouts": 1.5,
            },
        ],
        "actuals": {"Mookie Betts": {"hits": 1, "home_runs": 0, "strikeouts": 2}},
    },
    {
        "game_id": "HOU-TEX-2026-05-21",
        "status": "final",
        "innings": 9,
        "players": [
            {
                "player_name": "Yordan Alvarez", "player_type": "batter", "team": "HOU",
                "batting_order": 3, "handedness": "L", "opposing_pitcher_hand": "R",
                "hits_per_game": 1.5, "hits_last5_per_game": 2.0,
                "hr_per_game": 0.3, "hr_last5_per_game": 0.4,
                "k_per_game": 1.5, "k_last5_per_game": 1.2,
                "park_factor": 0.52, "temp_f": 90, "wind_direction": "out",
                "team_implied_total": 5.5, "home_away": "away",
                "opp_k_rate": 0.20, "market_agreement": 0.65,
                "line_hits": 1.5, "line_home_runs": 0.5, "line_strikeouts": 1.5,
            },
        ],
        "actuals": {"Yordan Alvarez": {"hits": 3, "home_runs": 1, "strikeouts": 0}},
    },
    {
        "game_id": "ATL-PHI-2026-05-21",
        "status": "final",
        "innings": 9,
        "players": [
            {
                "player_name": "Ronald Acuna Jr", "player_type": "batter", "team": "ATL",
                "batting_order": 1, "handedness": "R", "opposing_pitcher_hand": "L",
                "hits_per_game": 1.6, "hits_last5_per_game": 1.4,
                "hr_per_game": 0.25, "hr_last5_per_game": 0.2,
                "k_per_game": 1.3, "k_last5_per_game": 1.6,
                "park_factor": 0.50, "temp_f": 72, "wind_direction": "cross",
                "team_implied_total": 4.8, "home_away": "away",
                "opp_k_rate": 0.24, "market_agreement": 0.6,
                "line_hits": 1.5, "line_home_runs": 0.5, "line_strikeouts": 1.5,
            },
        ],
        "actuals": {"Ronald Acuna Jr": {"hits": 1, "home_runs": 0, "strikeouts": 2}},
    },
    {
        "game_id": "SEA-OAK-2026-05-22",
        "status": "final",
        "innings": 9,
        "players": [
            {
                "player_name": "Julio Rodriguez", "player_type": "batter", "team": "SEA",
                "batting_order": 2, "handedness": "R", "opposing_pitcher_hand": "R",
                "hits_per_game": 1.2, "hits_last5_per_game": 1.6,
                "hr_per_game": 0.2, "hr_last5_per_game": 0.4,
                "k_per_game": 1.6, "k_last5_per_game": 1.2,
                "park_factor": 0.45, "temp_f": 60, "wind_direction": "in",
                "team_implied_total": 4.2, "home_away": "away",
                "opp_k_rate": 0.28, "market_agreement": 0.55,
                "line_hits": 1.5, "line_home_runs": 0.5, "line_strikeouts": 1.5,
            },
        ],
        "actuals": {"Julio Rodriguez": {"hits": 2, "home_runs": 1, "strikeouts": 1}},
    },
    {
        "game_id": "CHC-STL-2026-05-22",
        "status": "final",
        "innings": 9,
        "players": [
            {
                "player_name": "Ian Happ", "player_type": "batter", "team": "CHC",
                "batting_order": 3, "handedness": "L", "opposing_pitcher_hand": "R",
                "hits_per_game": 1.1, "hits_last5_per_game": 1.4,
                "hr_per_game": 0.2, "hr_last5_per_game": 0.2,
                "k_per_game": 1.4, "k_last5_per_game": 1.8,
                "park_factor": 0.50, "temp_f": 75, "wind_direction": "out to left",
                "team_implied_total": 4.6, "home_away": "away",
                "opp_k_rate": 0.21, "market_agreement": 0.5,
                "line_hits": 0.5, "line_home_runs": 0.5, "line_strikeouts": 1.5,
            },
        ],
        "actuals": {"Ian Happ": {"hits": 1, "home_runs": 0, "strikeouts": 2}},
    },
    {
        "game_id": "MIN-CLE-2026-05-23",
        "status": "final",
        "innings": 9,
        "players": [
            {
                "player_name": "Byron Buxton", "player_type": "batter", "team": "MIN",
                "batting_order": 4, "handedness": "R", "opposing_pitcher_hand": "L",
                "hits_per_game": 1.0, "hits_last5_per_game": 1.4,
                "hr_per_game": 0.3, "hr_last5_per_game": 0.6,
                "k_per_game": 2.0, "k_last5_per_game": 1.6,
                "park_factor": 0.48, "temp_f": 55, "wind_direction": "cross",
                "team_implied_total": 4.0, "home_away": "away",
                "opp_k_rate": 0.26, "market_agreement": 0.6,
                "line_hits": 0.5, "line_home_runs": 0.5, "line_strikeouts": 1.5,
            },
        ],
        "actuals": {"Byron Buxton": {"hits": 1, "home_runs": 1, "strikeouts": 1}},
    },
    {
        "game_id": "DET-KC-2026-05-23",
        "status": "final",
        "innings": 9,
        "players": [
            {
                "player_name": "Riley Greene", "player_type": "batter", "team": "DET",
                "batting_order": 2, "handedness": "L", "opposing_pitcher_hand": "R",
                "hits_per_game": 1.3, "hits_last5_per_game": 1.6,
                "hr_per_game": 0.15, "hr_last5_per_game": 0.2,
                "k_per_game": 1.3, "k_last5_per_game": 1.0,
                "park_factor": 0.52, "temp_f": 80, "wind_direction": "out",
                "team_implied_total": 4.4, "home_away": "home",
                "opp_k_rate": 0.22, "market_agreement": 0.55,
                "line_hits": 1.5, "line_home_runs": 0.5, "line_strikeouts": 1.5,
            },
        ],
        "actuals": {"Riley Greene": {"hits": 2, "home_runs": 0, "strikeouts": 1}},
    },
    {
        "game_id": "CIN-MIL-2026-05-24",
        "status": "final",
        "innings": 9,
        "players": [
            {
                "player_name": "Elly De La Cruz", "player_type": "batter", "team": "CIN",
                "batting_order": 1, "handedness": "L", "opposing_pitcher_hand": "R",
                "hits_per_game": 1.4, "hits_last5_per_game": 2.0,
                "hr_per_game": 0.25, "hr_last5_per_game": 0.4,
                "k_per_game": 2.2, "k_last5_per_game": 1.8,
                "park_factor": 0.50, "temp_f": 70, "wind_direction": "cross",
                "team_implied_total": 5.0, "home_away": "away",
                "opp_k_rate": 0.23, "market_agreement": 0.65,
                "line_hits": 1.5, "line_home_runs": 0.5, "line_strikeouts": 2.5,
            },
        ],
        "actuals": {"Elly De La Cruz": {"hits": 3, "home_runs": 1, "strikeouts": 2}},
    },
    {
        "game_id": "TB-BAL-2026-05-24",
        "status": "final",
        "innings": 9,
        "players": [
            {
                "player_name": "Gunnar Henderson", "player_type": "batter", "team": "BAL",
                "batting_order": 2, "handedness": "L", "opposing_pitcher_hand": "R",
                "hits_per_game": 1.5, "hits_last5_per_game": 1.8,
                "hr_per_game": 0.3, "hr_last5_per_game": 0.4,
                "k_per_game": 1.5, "k_last5_per_game": 1.2,
                "park_factor": 0.55, "hr_factor": 0.58, "temp_f": 75,
                "wind_direction": "out to right", "team_implied_total": 5.0,
                "home_away": "home", "opp_k_rate": 0.24, "market_agreement": 0.7,
                "line_hits": 1.5, "line_home_runs": 0.5, "line_strikeouts": 1.5,
            },
        ],
        "actuals": {"Gunnar Henderson": {"hits": 2, "home_runs": 1, "strikeouts": 1}},
    },
]


def _compute_hit_rate(
    results: list[dict[str, Any]], *, market_filter: str | None = None
) -> dict[str, Any]:
    wins = 0
    losses = 0
    pushes = 0
    voids = 0

    for r in results:
        if market_filter and r["market"] != market_filter:
            continue
        result = r["result"]
        if result == SettlementResult.WIN:
            wins += 1
        elif result == SettlementResult.LOSS:
            losses += 1
        elif result == SettlementResult.PUSH:
            pushes += 1
        elif result == SettlementResult.VOID:
            voids += 1

    decided = wins + losses
    hit_rate = wins / decided if decided > 0 else None

    return {
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "voids": voids,
        "decided": decided,
        "hit_rate": hit_rate,
    }


def run_validation(*, market_filter: str | None = None) -> dict[str, Any]:
    all_results: list[dict[str, Any]] = []

    for game in _SAMPLE_GAMES:
        players = game["players"]
        markets = ("hits", "home_runs", "strikeouts")
        scored = score_baseball_props(players, markets=markets)

        picks_for_settlement = [
            {
                "player": s["player"],
                "market": s["market"],
                "direction": s["direction"],
                "line": s["line"],
            }
            for s in scored
        ]

        graded = grade_game_outcomes(
            picks=picks_for_settlement,
            actuals=game["actuals"],
            game_status=game["status"],
            innings_played=game.get("innings"),
        )
        all_results.extend(graded)

    stats = _compute_hit_rate(all_results, market_filter=market_filter)
    return {
        "games_evaluated": len(_SAMPLE_GAMES),
        "total_picks": len(all_results),
        "market_filter": market_filter or "all",
        **stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MLB validation harness")
    parser.add_argument("--market", type=str, default=None, help="Filter by market")
    args = parser.parse_args()

    print("=" * 60)
    print("MLB VALIDATION HARNESS")
    print("=" * 60)

    results = run_validation(market_filter=args.market)

    print(f"\nGames evaluated: {results['games_evaluated']}")
    print(f"Total picks graded: {results['total_picks']}")
    print(f"Market filter: {results['market_filter']}")
    print("\nResults:")
    print(f"  Wins:   {results['wins']}")
    print(f"  Losses: {results['losses']}")
    print(f"  Pushes: {results['pushes']}")
    print(f"  Voids:  {results['voids']}")
    print(f"  Decided: {results['decided']}")

    if results["hit_rate"] is not None:
        print(f"\n  HIT RATE: {results['hit_rate'] * 100:.1f}%")
    else:
        print("\n  HIT RATE: N/A (no decided picks)")

    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
