"""Basketball sport module with config-driven scoring.

Implements the SportModule protocol for basketball. Orchestrates LLM
providers (game context, player stats, prop lines) and feeds results
through the weighted-factor scoring engine.
"""

from __future__ import annotations

from typing import Any

from basketball_scoring import score_basketball_props


_BASKETBALL_MARKETS = {
    "points", "rebounds", "assists", "threes",
    "steals", "blocks", "turnovers", "fantasy_score",
}

_PLACEHOLDER_PLAYERS = [
    {"player_name": "LeBron James", "team": "LAL", "position": "SF",
     "minutes_proj": 35.0, "usage_rate": 0.28, "points_avg": 25.5,
     "points_last5": 27.0, "assist_avg": 7.2, "assist_last5": 7.8,
     "rebound_avg": 7.5, "rebound_last5": 8.0, "threes_avg": 2.3,
     "threes_last5": 2.5, "three_point_attempts": 5.5,
     "rotation_risk": "locked_in", "is_starter": True},
    {"player_name": "Anthony Davis", "team": "LAL", "position": "PF",
     "minutes_proj": 34.0, "usage_rate": 0.27, "points_avg": 24.0,
     "points_last5": 26.0, "assist_avg": 3.2, "assist_last5": 3.5,
     "rebound_avg": 10.5, "rebound_last5": 11.0, "threes_avg": 1.5,
     "threes_last5": 1.8, "three_point_attempts": 3.0,
     "rotation_risk": "normal", "is_starter": True},
    {"player_name": "Jayson Tatum", "team": "BOS", "position": "SF",
     "minutes_proj": 36.0, "usage_rate": 0.30, "points_avg": 27.0,
     "points_last5": 29.0, "assist_avg": 4.5, "assist_last5": 5.0,
     "rebound_avg": 8.5, "rebound_last5": 8.0, "threes_avg": 3.0,
     "threes_last5": 3.5, "three_point_attempts": 8.0,
     "rotation_risk": "locked_in", "is_starter": True},
    {"player_name": "Jaylen Brown", "team": "BOS", "position": "SG",
     "minutes_proj": 34.0, "usage_rate": 0.26, "points_avg": 23.0,
     "points_last5": 22.0, "assist_avg": 3.5, "assist_last5": 3.0,
     "rebound_avg": 5.5, "rebound_last5": 5.5, "threes_avg": 2.0,
     "threes_last5": 2.2, "three_point_attempts": 5.5,
     "rotation_risk": "normal", "is_starter": True},
]

_PLACEHOLDER_LINES: dict[str, dict[str, float]] = {
    "LeBron James": {"points": 25.5, "rebounds": 7.5, "assists": 7.5, "threes": 2.5, "steals": 1.5, "blocks": 0.5, "turnovers": 3.5, "fantasy_score": 45.5},
    "Anthony Davis": {"points": 24.5, "rebounds": 10.5, "assists": 3.5, "threes": 1.5, "steals": 1.5, "blocks": 2.5, "turnovers": 2.5, "fantasy_score": 44.5},
    "Jayson Tatum": {"points": 27.5, "rebounds": 8.5, "assists": 4.5, "threes": 3.5, "steals": 1.5, "blocks": 0.5, "turnovers": 2.5, "fantasy_score": 46.5},
    "Jaylen Brown": {"points": 23.5, "rebounds": 5.5, "assists": 3.5, "threes": 2.5, "steals": 1.5, "blocks": 0.5, "turnovers": 2.5, "fantasy_score": 38.5},
}


class BasketballModule:
    def __init__(
        self,
        *,
        game_provider: Any | None = None,
        stats_provider: Any | None = None,
        props_provider: Any | None = None,
        allow_deterministic_fallback: bool = True,
    ) -> None:
        self._game_provider = game_provider
        self._stats_provider = stats_provider
        self._props_provider = props_provider
        self._allow_fallback = allow_deterministic_fallback

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
        game_ctx = self._fetch_game_context(home_team, away_team, match_date)
        players = self._fetch_player_stats(home_team, away_team, match_date)
        lines = self._fetch_prop_lines(players)

        if players is None and self._allow_fallback:
            players = list(_PLACEHOLDER_PLAYERS)
            lines = dict(_PLACEHOLDER_LINES)

        return {
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "league": league or "nba",
            "game": game_ctx or {},
            "players": players or [],
            "lines": lines or {},
        }

    def score(
        self, match_inputs: dict[str, Any], *, markets: tuple[str, ...] = ()
    ) -> list[dict[str, Any]]:
        target_markets = set(markets) if markets else {"points", "rebounds", "assists", "threes"}
        scoring_markets = tuple(m for m in target_markets if m in ("points", "rebounds", "assists", "threes"))

        players = match_inputs.get("players", [])
        lines = match_inputs.get("lines", {})
        game = match_inputs.get("game", {})

        player_dicts = self._build_scoring_dicts(players, lines, game)

        if scoring_markets and player_dicts:
            scores = score_basketball_props(player_dicts, markets=scoring_markets)
        else:
            scores = []

        unsupported_markets = target_markets - {"points", "rebounds", "assists", "threes"}
        for player in players:
            name = player.get("player_name", "Unknown")
            player_lines = lines.get(name, {})
            for market in unsupported_markets:
                if market not in player_lines:
                    continue
                line = player_lines[market]
                if isinstance(line, dict):
                    line = line.get("line", 0)
                scores.append({
                    "player": name,
                    "market": market,
                    "line": line,
                    "direction": "over",
                    "score": 0.5,
                    "confidence": "low",
                    "explainability": {"risk_flags": ["unsupported_market"], "top_contributing_factors": []},
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

    def _fetch_game_context(
        self, home_team: str, away_team: str, match_date: str,
    ) -> dict[str, Any] | None:
        if self._game_provider is None:
            return None
        try:
            return self._game_provider.lookup_game(
                home_team=home_team, away_team=away_team, match_date=match_date,
            )
        except Exception:
            return None

    def _fetch_player_stats(
        self, home_team: str, away_team: str, match_date: str,
    ) -> list[dict[str, Any]] | None:
        if self._stats_provider is None:
            return None
        try:
            return self._stats_provider.get_player_stats(
                home_team=home_team, away_team=away_team, match_date=match_date,
            )
        except Exception:
            return None

    def _fetch_prop_lines(
        self, players: list[dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        if self._props_provider is None or not players:
            return None
        try:
            return self._props_provider.get_prop_lines(
                players=players,
                markets=("points", "rebounds", "assists", "threes"),
            )
        except Exception:
            return None

    @staticmethod
    def _build_scoring_dicts(
        players: list[dict[str, Any]],
        lines: dict[str, Any],
        game: dict[str, Any],
    ) -> list[dict[str, Any]]:
        pace_factor = None
        if game.get("projected_game_pace"):
            pace_factor = game["projected_game_pace"] / 100.0

        dicts: list[dict[str, Any]] = []
        for player in players:
            name = player.get("player_name", "Unknown")
            player_lines = lines.get(name, {})

            d: dict[str, Any] = dict(player)

            if pace_factor is not None:
                d["pace_factor"] = pace_factor

            if game.get("home_rest_days") is not None and "rest_days" not in d:
                team = d.get("team", "")
                if game.get("home_team", "").upper().startswith(team[:3].upper()):
                    d["rest_days"] = game["home_rest_days"]
                else:
                    d["rest_days"] = game.get("away_rest_days")

            for market in ("points", "assists", "rebounds", "threes"):
                line_key = f"line_{market}"
                if line_key not in d:
                    market_data = player_lines.get(market, {})
                    if isinstance(market_data, dict):
                        d[line_key] = market_data.get("line", 0)
                        if market_data.get("market_agreement") is not None:
                            d["market_agreement"] = market_data["market_agreement"]
                    elif isinstance(market_data, (int, float)):
                        d[line_key] = market_data

            dicts.append(d)
        return dicts
