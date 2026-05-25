"""Baseball sport module with placeholder scoring.

Implements the SportModule protocol for baseball. Uses demo/placeholder
data until real MLB providers are wired in.
"""

from __future__ import annotations

from typing import Any


_BASEBALL_MARKETS = {
    "hits", "total_bases", "runs", "rbi",
    "home_runs", "strikeouts", "walks", "pitcher_outs",
}

_PLACEHOLDER_PLAYERS = [
    {"player_name": "Aaron Judge", "team": "NYY", "position": "RF", "type": "batter"},
    {"player_name": "Juan Soto", "team": "NYY", "position": "LF", "type": "batter"},
    {"player_name": "Rafael Devers", "team": "BOS", "position": "3B", "type": "batter"},
    {"player_name": "Gerrit Cole", "team": "NYY", "position": "SP", "type": "pitcher"},
]

_PLACEHOLDER_LINES: dict[str, dict[str, float]] = {
    "Aaron Judge": {"hits": 1.5, "total_bases": 2.5, "runs": 0.5, "rbi": 1.5, "home_runs": 0.5, "strikeouts": 1.5, "walks": 0.5},
    "Juan Soto": {"hits": 1.5, "total_bases": 2.5, "runs": 0.5, "rbi": 0.5, "home_runs": 0.5, "strikeouts": 1.5, "walks": 1.5},
    "Rafael Devers": {"hits": 1.5, "total_bases": 2.5, "runs": 0.5, "rbi": 1.5, "home_runs": 0.5, "strikeouts": 1.5, "walks": 0.5},
    "Gerrit Cole": {"pitcher_outs": 17.5, "strikeouts": 7.5, "hits": 5.5, "walks": 2.5},
}


class BaseballModule:
    @property
    def sport_id(self) -> str:
        return "baseball"

    @property
    def supported_leagues(self) -> set[str]:
        return {"mlb"}

    @property
    def supported_markets(self) -> set[str]:
        return set(_BASEBALL_MARKETS)

    def collect_inputs(
        self, *, home_team: str, away_team: str, match_date: str, league: str | None = None
    ) -> dict[str, Any]:
        return {
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "league": league or "mlb",
            "players": list(_PLACEHOLDER_PLAYERS),
            "lines": dict(_PLACEHOLDER_LINES),
        }

    def score(
        self, match_inputs: dict[str, Any], *, markets: tuple[str, ...] = ()
    ) -> list[dict[str, Any]]:
        from baseball_scoring import score_baseball_props

        target_markets = tuple(markets) if markets else tuple(_BASEBALL_MARKETS)
        players = match_inputs.get("players", [])
        lines = match_inputs.get("lines", _PLACEHOLDER_LINES)

        scoring_input = []
        for player in players:
            if isinstance(player, dict) and "player_name" in player:
                entry = dict(player)
                name = entry["player_name"]
                player_lines = lines.get(name, {})
                for market, line_val in player_lines.items():
                    entry[f"line_{market}"] = line_val
                scoring_input.append(entry)

        if scoring_input:
            return score_baseball_props(scoring_input, markets=target_markets)

        return []

    def explain(self, scored_pick: dict[str, Any]) -> str:
        from baseball_explainer import build_deterministic_explanation

        return build_deterministic_explanation(scored_pick)
