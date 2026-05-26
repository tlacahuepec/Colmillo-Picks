"""Baseball sport module with MLB StatsAPI provider support.

Implements the SportModule protocol for baseball. When an MLBCollectionService
is provided, fetches real lineup/pitcher/stats data from the MLB StatsAPI.
Falls back to placeholder data when no service is configured or when the
requested game cannot be found.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from mlb_collection import MLBCollectionService

logger = logging.getLogger(__name__)

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

_MLB_TEAM_ALIASES: dict[str, str] = {
    "ari": "arizona diamondbacks", "dbacks": "arizona diamondbacks", "diamondbacks": "arizona diamondbacks",
    "atl": "atlanta braves", "braves": "atlanta braves",
    "bal": "baltimore orioles", "orioles": "baltimore orioles",
    "bos": "boston red sox", "red sox": "boston red sox",
    "chc": "chicago cubs", "cubs": "chicago cubs",
    "chw": "chicago white sox", "white sox": "chicago white sox",
    "cin": "cincinnati reds", "reds": "cincinnati reds",
    "cle": "cleveland guardians", "guardians": "cleveland guardians",
    "col": "colorado rockies", "rockies": "colorado rockies",
    "det": "detroit tigers", "tigers": "detroit tigers",
    "hou": "houston astros", "astros": "houston astros",
    "kc": "kansas city royals", "royals": "kansas city royals",
    "laa": "los angeles angels", "angels": "los angeles angels",
    "lad": "los angeles dodgers", "dodgers": "los angeles dodgers",
    "mia": "miami marlins", "marlins": "miami marlins",
    "mil": "milwaukee brewers", "brewers": "milwaukee brewers",
    "min": "minnesota twins", "twins": "minnesota twins",
    "nym": "new york mets", "mets": "new york mets",
    "nyy": "new york yankees", "yankees": "new york yankees",
    "oak": "oakland athletics", "athletics": "oakland athletics",
    "phi": "philadelphia phillies", "phillies": "philadelphia phillies",
    "pit": "pittsburgh pirates", "pirates": "pittsburgh pirates",
    "sd": "san diego padres", "padres": "san diego padres",
    "sf": "san francisco giants", "giants": "san francisco giants",
    "sea": "seattle mariners", "mariners": "seattle mariners",
    "stl": "st. louis cardinals", "cardinals": "st. louis cardinals",
    "tb": "tampa bay rays", "rays": "tampa bay rays",
    "tex": "texas rangers", "rangers": "texas rangers",
    "tor": "toronto blue jays", "blue jays": "toronto blue jays",
    "wsh": "washington nationals", "nationals": "washington nationals",
}


def _resolve_team(name: str) -> str:
    lower = name.strip().lower()
    return _MLB_TEAM_ALIASES.get(lower, lower)


def _find_game(games: list[dict[str, Any]], home_team: str, away_team: str) -> dict[str, Any] | None:
    home_resolved = _resolve_team(home_team)
    away_resolved = _resolve_team(away_team)
    for game in games:
        teams = game.get("teams", {})
        game_home = teams.get("home", {}).get("team", {}).get("name", "").lower()
        game_away = teams.get("away", {}).get("team", {}).get("name", "").lower()
        if home_resolved in game_home or game_home in home_resolved:
            if away_resolved in game_away or game_away in away_resolved:
                return game
    return None


def _context_to_scoring_input(ctx: Any) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    players: list[dict[str, Any]] = []
    lines: dict[str, dict[str, float]] = {}

    for order in [ctx.home_batting_order, ctx.away_batting_order]:
        if order is None:
            continue
        for slot in order.slots:
            players.append({
                "player_name": slot.player_name,
                "team": order.team,
                "position": slot.field_position or "?",
                "type": "batter",
                "batting_order": slot.position,
                "player_id": slot.player_id,
            })
            lines[slot.player_name] = {}

    for pitcher, team in [
        (ctx.home_probable_pitcher, ctx.game.home_team),
        (ctx.away_probable_pitcher, ctx.game.away_team),
    ]:
        if pitcher:
            players.append({
                "player_name": pitcher.player_name,
                "team": team,
                "position": "SP",
                "type": "pitcher",
                "player_id": pitcher.player_id,
            })
            lines[pitcher.player_name] = {}

    return players, lines


class BaseballModule:
    def __init__(self, *, collection_service: "MLBCollectionService | None" = None) -> None:
        self._collection_service = collection_service

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
        if self._collection_service is not None:
            try:
                return self._collect_live(home_team, away_team, match_date, league)
            except Exception as exc:
                logger.warning("MLB live collection failed, using fallback: %s", exc)

        return self._collect_placeholder(home_team, away_team, match_date, league)

    def _collect_live(
        self, home_team: str, away_team: str, match_date: str, league: str | None
    ) -> dict[str, Any]:
        from baseball_domain import MLBGame

        schedule_result = self._collection_service._schedule.get_schedule(date=match_date)

        if not schedule_result.meta.available or not schedule_result.games:
            logger.info("Schedule unavailable or empty for %s", match_date)
            return self._collect_placeholder(home_team, away_team, match_date, league)

        game_data = _find_game(schedule_result.games, home_team, away_team)
        if game_data is None:
            logger.info("Game not found in schedule for %s vs %s on %s", home_team, away_team, match_date)
            return self._collect_placeholder(home_team, away_team, match_date, league)

        game_pk = game_data["gamePk"]
        teams = game_data.get("teams", {})
        game = MLBGame(
            event_id=str(game_pk),
            home_team=teams.get("home", {}).get("team", {}).get("name", home_team),
            away_team=teams.get("away", {}).get("team", {}).get("name", away_team),
            venue=game_data.get("venue", {}).get("name", ""),
            game_time_utc=game_data.get("gameDate", ""),
            home_team_id=teams.get("home", {}).get("team", {}).get("id"),
            away_team_id=teams.get("away", {}).get("team", {}).get("id"),
            venue_id=game_data.get("venue", {}).get("id"),
        )

        logger.info("Collecting data for game %d: %s vs %s", game_pk, game.home_team, game.away_team)
        ctx = self._collection_service.collect(game_pk=game_pk, game=game)
        players, lines = _context_to_scoring_input(ctx)

        if not players:
            logger.warning(
                "No players extracted for game %d — pitchers: home=%s away=%s, lineups: home=%s away=%s",
                game_pk,
                ctx.home_probable_pitcher is not None,
                ctx.away_probable_pitcher is not None,
                ctx.home_batting_order is not None,
                ctx.away_batting_order is not None,
            )
            return self._collect_placeholder(home_team, away_team, match_date, league)

        logger.info("Live collection succeeded: %d players for game %d", len(players), game_pk)
        return {
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "league": league or "mlb",
            "players": players,
            "lines": lines,
        }

    def _collect_placeholder(
        self, home_team: str, away_team: str, match_date: str, league: str | None
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

