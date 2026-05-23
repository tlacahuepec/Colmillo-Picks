"""Basketball sport module with placeholder scoring.

Implements the SportModule protocol for basketball. Uses demo/placeholder
data until real NBA providers are wired in.
"""

from __future__ import annotations

from typing import Any


_BASKETBALL_MARKETS = {
    "points", "rebounds", "assists", "threes",
    "steals", "blocks", "turnovers", "fantasy_score",
}

_PLACEHOLDER_PLAYERS = [
    {"player_name": "LeBron James", "team": "LAL", "position": "SF"},
    {"player_name": "Anthony Davis", "team": "LAL", "position": "PF"},
    {"player_name": "Jayson Tatum", "team": "BOS", "position": "SF"},
    {"player_name": "Jaylen Brown", "team": "BOS", "position": "SG"},
]

_PLACEHOLDER_LINES: dict[str, dict[str, float]] = {
    "LeBron James": {"points": 25.5, "rebounds": 7.5, "assists": 7.5, "threes": 2.5, "steals": 1.5, "blocks": 0.5, "turnovers": 3.5, "fantasy_score": 45.5},
    "Anthony Davis": {"points": 24.5, "rebounds": 10.5, "assists": 3.5, "threes": 1.5, "steals": 1.5, "blocks": 2.5, "turnovers": 2.5, "fantasy_score": 44.5},
    "Jayson Tatum": {"points": 27.5, "rebounds": 8.5, "assists": 4.5, "threes": 3.5, "steals": 1.5, "blocks": 0.5, "turnovers": 2.5, "fantasy_score": 46.5},
    "Jaylen Brown": {"points": 23.5, "rebounds": 5.5, "assists": 3.5, "threes": 2.5, "steals": 1.5, "blocks": 0.5, "turnovers": 2.5, "fantasy_score": 38.5},
}


class BasketballModule:
    @property
    def sport_id(self) -> str:
        return "basketball"

    @property
    def supported_leagues(self) -> set[str]:
        return {"nba", "euroleague", "ncaab"}

    @property
    def supported_markets(self) -> set[str]:
        return set(_BASKETBALL_MARKETS)

    def collect_inputs(
        self, *, home_team: str, away_team: str, match_date: str, league: str | None = None
    ) -> dict[str, Any]:
        return {
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "league": league or "nba",
            "players": list(_PLACEHOLDER_PLAYERS),
            "lines": dict(_PLACEHOLDER_LINES),
        }

    def score(
        self, match_inputs: dict[str, Any], *, markets: tuple[str, ...] = ()
    ) -> list[dict[str, Any]]:
        target_markets = set(markets) if markets else _BASKETBALL_MARKETS
        players = match_inputs.get("players", [])
        lines = match_inputs.get("lines", _PLACEHOLDER_LINES)

        scores: list[dict[str, Any]] = []
        for player in players:
            name = player["player_name"]
            player_lines = lines.get(name, {})
            for market in target_markets:
                if market not in player_lines:
                    continue
                line = player_lines[market]
                scores.append({
                    "player": name,
                    "market": market,
                    "line": line,
                    "direction": "over",
                    "score": 0.6,
                    "confidence": "medium",
                    "explainability": {"risk_flags": ["placeholder_scoring"]},
                })

        return scores

    def explain(self, scored_pick: dict[str, Any]) -> str:
        player = scored_pick.get("player", "Unknown")
        market = scored_pick.get("market", "unknown")
        direction = scored_pick.get("direction", "over")
        line = scored_pick.get("line", 0)
        confidence = scored_pick.get("confidence", "medium")
        return (
            f"{player}: {direction} {line} {market} "
            f"(confidence: {confidence})"
        )
