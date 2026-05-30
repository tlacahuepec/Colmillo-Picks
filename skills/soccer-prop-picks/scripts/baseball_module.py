"""Baseball sport module with MLB StatsAPI provider support.

Implements the SportModule protocol for baseball. When an MLBCollectionService
is provided, fetches real lineup/pitcher/stats data from the MLB StatsAPI.
Deterministic sample data is only available through explicit opt-in.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from missing_input_enrichment import (
    mark_enrichment_failed,
    merge_enriched_inputs,
    pick_input_provenance,
)

if TYPE_CHECKING:
    from mlb_collection import MLBCollectionService

logger = logging.getLogger("colmillo.baseball")

_BASEBALL_MARKETS = {
    "hits", "total_bases", "runs", "rbi",
    "home_runs", "strikeouts", "walks", "pitcher_outs",
}
_HITTER_MARKETS = {"hits", "total_bases", "runs", "rbi", "home_runs"}
_PITCHER_MARKETS = {"strikeouts", "pitcher_outs", "walks"}

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


class BaseballDataQualityError(RuntimeError):
    """Raised when baseball data is too incomplete to produce recommendations."""

    def __init__(self, message: str, *, reason: str) -> None:
        self.reason = reason
        super().__init__(message)


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
        if home_resolved in game_away or game_away in home_resolved:
            if away_resolved in game_home or game_home in away_resolved:
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

    for prop_line in getattr(ctx, "prop_lines", []) or []:
        player_name = getattr(prop_line, "player_name", "")
        market = getattr(prop_line, "market", "")
        line = getattr(prop_line, "line", None)
        if player_name and market and line is not None:
            lines.setdefault(player_name, {})[market] = line

    return players, lines


class BaseballModule:
    def __init__(
        self,
        *,
        collection_service: "MLBCollectionService | None" = None,
        enrichment_provider: Any | None = None,
        allow_deterministic_fallback: bool = False,
    ) -> None:
        self._collection_service = collection_service
        self._enrichment_provider = enrichment_provider
        self._allow_deterministic_fallback = allow_deterministic_fallback

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
        if self._collection_service is None:
            return self._reject_or_fallback(
                reason="collection_service_unavailable",
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                league=league,
            )

        try:
            return self._collect_live(home_team, away_team, match_date, league)
        except BaseballDataQualityError:
            raise
        except Exception as exc:
            return self._reject_or_fallback(
                reason="live_collection_exception",
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                league=league,
                error=exc,
            )

    def _collect_live(
        self, home_team: str, away_team: str, match_date: str, league: str | None
    ) -> dict[str, Any]:
        from baseball_domain import MLBGame

        schedule_result = self._collection_service._schedule.get_schedule(date=match_date)

        if not schedule_result.meta.available or not schedule_result.games:
            return self._reject_or_fallback(
                reason="schedule_unavailable",
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                league=league,
            )

        game_data = _find_game(schedule_result.games, home_team, away_team)
        if game_data is None:
            return self._reject_or_fallback(
                reason="game_not_found",
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                league=league,
            )

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
        collection_summary = _collection_summary(
            ctx=ctx,
            game=game,
            players=players,
            lines=lines,
        )

        if not players:
            return self._reject_or_fallback(
                reason="no_players_extracted",
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                league=league,
                context=collection_summary,
            )

        logger.info(
            "Live collection succeeded: source=mlb_statsapi game_pk=%s players=%s "
            "batters=%s pitchers=%s prop_lines=%s home_lineup_players=%s away_lineup_players=%s",
            game_pk,
            collection_summary["player_count"],
            collection_summary["batter_count"],
            collection_summary["pitcher_count"],
            collection_summary["prop_line_count"],
            collection_summary["home_lineup_players"],
            collection_summary["away_lineup_players"],
        )
        return {
            "home_team": game.home_team,
            "away_team": game.away_team,
            "match_date": match_date,
            "league": league or "mlb",
            "venue": game.venue,
            "game_time_utc": game.game_time_utc,
            "home_probable_pitcher": (
                ctx.home_probable_pitcher.player_name if ctx.home_probable_pitcher else None
            ),
            "away_probable_pitcher": (
                ctx.away_probable_pitcher.player_name if ctx.away_probable_pitcher else None
            ),
            "players": players,
            "lines": lines,
            "data_quality": _data_quality_from_context(ctx),
            "collection_summary": collection_summary,
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
            "data_quality": {
                "source": "deterministic_fallback",
                "lineup_status": "mock",
                "pitcher_status": "mock",
                "weather_status": "mock",
                "odds_status": "mock",
            },
        }

    def score(
        self, match_inputs: dict[str, Any], *, markets: tuple[str, ...] = ()
    ) -> list[dict[str, Any]]:
        from baseball_scoring import score_baseball_props

        target_markets = tuple(markets) if markets else tuple(_BASEBALL_MARKETS)
        enrichment_attempted = False

        while True:
            players = match_inputs.get("players", [])
            lines = match_inputs.get("lines", {})

            if _HITTER_MARKETS.intersection(target_markets) and not any(
                _is_batter(player) for player in players if isinstance(player, dict)
            ):
                if not enrichment_attempted and self._attempt_enrichment(
                    match_inputs=match_inputs,
                    markets=target_markets,
                    missing_fields=["batters"],
                ):
                    enrichment_attempted = True
                    continue
                reason = _missing_batter_reason(match_inputs)
                _log_scoring_rejection(
                    reason=reason,
                    match_inputs=match_inputs,
                    markets=target_markets,
                )
                raise BaseballDataQualityError(
                    _missing_batter_message(match_inputs),
                    reason=reason,
                )

            scores: list[dict[str, Any]] = []
            missing_lines: list[str] = []
            for player in players:
                if isinstance(player, dict) and "player_name" in player:
                    entry = dict(player)
                    name = entry["player_name"]
                    player_lines = lines.get(name, {})
                    player_markets: list[str] = []
                    for market in target_markets:
                        if not _player_supports_market(entry, market):
                            continue
                        has_line, line_val = _line_for_market(player_lines, market)
                        if not has_line:
                            missing_lines.append(f"{name}:{market}")
                            continue
                        entry[f"line_{market}"] = line_val
                        if isinstance(player_lines.get(market), dict):
                            agreement = player_lines[market].get("market_agreement")
                            if agreement is not None:
                                entry["market_agreement"] = agreement
                        player_markets.append(market)
                    if player_markets:
                        scores.extend(score_baseball_props([entry], markets=tuple(player_markets)))

            if scores:
                return _attach_pick_provenance(scores, match_inputs)

            if missing_lines and not enrichment_attempted and self._attempt_enrichment(
                match_inputs=match_inputs,
                markets=target_markets,
                missing_fields=[f"prop_line:{item}" for item in missing_lines[:20]],
            ):
                enrichment_attempted = True
                continue

            if missing_lines:
                _log_scoring_rejection(
                    reason="missing_prop_lines",
                    match_inputs=match_inputs,
                    markets=target_markets,
                    context={"missing_lines": missing_lines[:10]},
                )
                raise BaseballDataQualityError(
                    "Could not find enough match details: missing prop lines for requested baseball markets.",
                    reason="missing_prop_lines",
                )

            return []

    def explain(self, scored_pick: dict[str, Any]) -> str:
        from baseball_explainer import build_deterministic_explanation

        return build_deterministic_explanation(scored_pick)

    def _attempt_enrichment(
        self,
        *,
        match_inputs: dict[str, Any],
        markets: tuple[str, ...],
        missing_fields: list[str],
    ) -> bool:
        if self._enrichment_provider is None:
            return False
        logger.info(
            "baseball_gemini_enrichment_attempt sport=baseball home_team=%s away_team=%s "
            "match_date=%s league=%s markets=%s missing_fields=%s provider=%s model=%s",
            match_inputs.get("home_team", ""),
            match_inputs.get("away_team", ""),
            match_inputs.get("match_date", ""),
            match_inputs.get("league", "mlb"),
            ",".join(markets),
            ",".join(missing_fields),
            type(self._enrichment_provider).__name__,
            getattr(self._enrichment_provider, "model", "unknown"),
        )
        try:
            enrichment = self._enrichment_provider.enrich_missing_inputs(
                sport="baseball",
                home_team=match_inputs.get("home_team", ""),
                away_team=match_inputs.get("away_team", ""),
                match_date=match_inputs.get("match_date", ""),
                league=match_inputs.get("league", "mlb"),
                requested_markets=markets,
                missing_fields=missing_fields,
                players=[p for p in match_inputs.get("players", []) if isinstance(p, dict)],
                lines=match_inputs.get("lines", {}),
                game={
                    "venue": match_inputs.get("venue"),
                    "game_time_utc": match_inputs.get("game_time_utc"),
                    "home_probable_pitcher": match_inputs.get("home_probable_pitcher"),
                    "away_probable_pitcher": match_inputs.get("away_probable_pitcher"),
                },
                official_context=match_inputs.get("collection_summary", {}),
            )
        except Exception as exc:
            mark_enrichment_failed(match_inputs, reason=str(exc), missing_fields=missing_fields)
            logger.warning(
                "baseball_gemini_enrichment_failed",
                extra={
                    "sport": "baseball",
                    "home_team": match_inputs.get("home_team", ""),
                    "away_team": match_inputs.get("away_team", ""),
                    "match_date": match_inputs.get("match_date", ""),
                    "league": match_inputs.get("league", "mlb"),
                    "markets": ",".join(markets),
                    "missing_fields": ",".join(missing_fields),
                    "provider": type(self._enrichment_provider).__name__,
                    "model": getattr(self._enrichment_provider, "model", "unknown"),
                    "error": str(exc),
                },
            )
            return False

        if not enrichment:
            mark_enrichment_failed(match_inputs, reason="empty_enrichment", missing_fields=missing_fields)
            logger.warning(
                "baseball_gemini_enrichment_incomplete",
                extra={
                    "sport": "baseball",
                    "home_team": match_inputs.get("home_team", ""),
                    "away_team": match_inputs.get("away_team", ""),
                    "match_date": match_inputs.get("match_date", ""),
                    "league": match_inputs.get("league", "mlb"),
                    "markets": ",".join(markets),
                    "missing_fields": ",".join(missing_fields),
                    "reason": "empty_enrichment",
                },
            )
            return False

        merge_enriched_inputs(match_inputs, enrichment)
        logger.info(
            "baseball_gemini_enrichment_success sport=baseball home_team=%s away_team=%s "
            "match_date=%s league=%s markets=%s missing_fields=%s enriched_players=%s enriched_line_players=%s",
            match_inputs.get("home_team", ""),
            match_inputs.get("away_team", ""),
            match_inputs.get("match_date", ""),
            match_inputs.get("league", "mlb"),
            ",".join(markets),
            ",".join(missing_fields),
            len(enrichment.get("players", []) or []),
            len(enrichment.get("lines", {}) or {}),
        )
        return True

    def _reject_or_fallback(
        self,
        *,
        reason: str,
        home_team: str,
        away_team: str,
        match_date: str,
        league: str | None,
        error: Exception | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        detail = _build_error_message(reason=reason)
        _log_rejection(
            reason=reason,
            home_team=home_team,
            away_team=away_team,
            match_date=match_date,
            league=league or "mlb",
            error=error,
            context=context,
        )
        if self._allow_deterministic_fallback:
            logger.warning(
                "baseball_deterministic_fallback_used",
                extra={
                    "sport": "baseball",
                    "reason": reason,
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                    "league": league or "mlb",
                },
            )
            return self._collect_placeholder(home_team, away_team, match_date, league)
        raise BaseballDataQualityError(detail, reason=reason) from error


def _build_error_message(*, reason: str) -> str:
    if reason == "game_not_found":
        return "Could not find enough match details: MLB game was not found for the requested teams/date."
    if reason == "schedule_unavailable":
        return "Could not find enough match details: MLB schedule was unavailable or empty."
    if reason == "collection_service_unavailable":
        return "Could not find enough match details: MLB collection service is unavailable."
    if reason == "no_players_extracted":
        return "Could not find enough match details: no MLB players were extracted for the game."
    return "Could not find enough match details: MLB data collection failed."


def _log_rejection(
    *,
    reason: str,
    home_team: str,
    away_team: str,
    match_date: str,
    league: str,
    error: Exception | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    logger.warning(
        f"baseball_collection_rejected reason={reason}",
        extra={
            "sport": "baseball",
            "reason": reason,
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "league": league,
            "error": str(error) if error else None,
            "context": context,
        },
    )


def _log_scoring_rejection(
    *,
    reason: str,
    match_inputs: dict[str, Any],
    markets: tuple[str, ...],
    context: dict[str, Any] | None = None,
) -> None:
    summary = _score_rejection_context(match_inputs, context)
    logger.warning(
        f"baseball_scoring_rejected reason={reason}",
        extra={
            "sport": "baseball",
            "reason": reason,
            "home_team": match_inputs.get("home_team", ""),
            "away_team": match_inputs.get("away_team", ""),
            "match_date": match_inputs.get("match_date", ""),
            "league": match_inputs.get("league", "mlb"),
            "markets": ",".join(markets),
            "source": summary.get("source", ""),
            "game_pk": summary.get("game_pk", ""),
            "venue": summary.get("venue", ""),
            "game_time_utc": summary.get("game_time_utc", ""),
            "player_count": summary.get("player_count", 0),
            "batter_count": summary.get("batter_count", 0),
            "pitcher_count": summary.get("pitcher_count", 0),
            "prop_line_count": summary.get("prop_line_count", 0),
            "home_lineup_players": summary.get("home_lineup_players", 0),
            "away_lineup_players": summary.get("away_lineup_players", 0),
            "context": context,
        },
    )


def _data_quality_from_context(ctx: Any) -> dict[str, Any]:
    provider_status = getattr(ctx, "provider_status", None)
    home_order = getattr(ctx, "home_batting_order", None)
    away_order = getattr(ctx, "away_batting_order", None)
    return {
        "source": "mlb_statsapi",
        "lineup_status": getattr(provider_status, "lineup", "unknown"),
        "pitcher_status": "ok"
        if (getattr(ctx, "home_probable_pitcher", None) or getattr(ctx, "away_probable_pitcher", None))
        else "unavailable",
        "weather_status": getattr(provider_status, "weather", "unknown"),
        "odds_status": getattr(provider_status, "odds", "unknown"),
        "home_lineup_players": len(getattr(home_order, "slots", []) or []),
        "away_lineup_players": len(getattr(away_order, "slots", []) or []),
    }


def _collection_summary(
    *,
    ctx: Any,
    game: Any,
    players: list[dict[str, Any]],
    lines: dict[str, dict[str, float]],
) -> dict[str, Any]:
    home_order = getattr(ctx, "home_batting_order", None)
    away_order = getattr(ctx, "away_batting_order", None)
    prop_lines = getattr(ctx, "prop_lines", []) or []
    return {
        "source": "mlb_statsapi",
        "game_found": True,
        "game_pk": getattr(game, "event_id", ""),
        "venue": getattr(game, "venue", ""),
        "game_time_utc": getattr(game, "game_time_utc", ""),
        "player_count": len(players),
        "batter_count": sum(1 for player in players if _is_batter(player)),
        "pitcher_count": sum(1 for player in players if _is_pitcher(player)),
        "prop_line_count": _prop_line_count(lines),
        "raw_prop_line_count": len(prop_lines),
        "home_lineup_players": len(getattr(home_order, "slots", []) or []),
        "away_lineup_players": len(getattr(away_order, "slots", []) or []),
        "home_probable_pitcher": (
            ctx.home_probable_pitcher.player_name if ctx.home_probable_pitcher else None
        ),
        "away_probable_pitcher": (
            ctx.away_probable_pitcher.player_name if ctx.away_probable_pitcher else None
        ),
        "rejection_reasons": list(getattr(ctx, "rejection_reasons", []) or []),
    }


def _score_rejection_context(
    match_inputs: dict[str, Any], extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    summary = dict(match_inputs.get("collection_summary") or {})
    players = [p for p in match_inputs.get("players", []) if isinstance(p, dict)]
    lines = match_inputs.get("lines", {})
    summary.setdefault("source", match_inputs.get("data_quality", {}).get("source", ""))
    summary.setdefault("game_found", bool(summary.get("game_pk")))
    summary.setdefault("game_pk", match_inputs.get("game_pk", ""))
    summary.setdefault("venue", match_inputs.get("venue", ""))
    summary.setdefault("game_time_utc", match_inputs.get("game_time_utc", ""))
    summary.setdefault("player_count", len(players))
    summary.setdefault("batter_count", sum(1 for player in players if _is_batter(player)))
    summary.setdefault("pitcher_count", sum(1 for player in players if _is_pitcher(player)))
    summary.setdefault("prop_line_count", _prop_line_count(lines))
    summary.setdefault(
        "home_lineup_players",
        match_inputs.get("data_quality", {}).get("home_lineup_players", 0),
    )
    summary.setdefault(
        "away_lineup_players",
        match_inputs.get("data_quality", {}).get("away_lineup_players", 0),
    )
    if extra:
        summary.update(extra)
    return summary


def _missing_batter_reason(match_inputs: dict[str, Any]) -> str:
    summary = _score_rejection_context(match_inputs)
    if summary.get("source") == "mlb_statsapi" and summary.get("game_found"):
        return "hitter_inputs_unavailable"
    return "missing_batter_data"


def _missing_batter_message(match_inputs: dict[str, Any]) -> str:
    summary = _score_rejection_context(match_inputs)
    if summary.get("source") == "mlb_statsapi" and summary.get("game_found"):
        return (
            "Could not find enough match details: MLB StatsAPI found the game, but hitter "
            "markets require official batting order data and prop lines; those inputs are "
            "unavailable for this game right now."
        )
    return "Could not find enough match details: hitter markets require batter data."


def _prop_line_count(lines: Any) -> int:
    if not isinstance(lines, dict):
        return 0
    return sum(len(player_lines) for player_lines in lines.values() if isinstance(player_lines, dict))


def _is_batter(player: dict[str, Any]) -> bool:
    player_type = str(player.get("type") or player.get("player_type") or "").lower()
    return player_type == "batter" or player.get("batting_order") is not None


def _is_pitcher(player: dict[str, Any]) -> bool:
    player_type = str(player.get("type") or player.get("player_type") or "").lower()
    position = str(player.get("position") or "").upper()
    return player_type == "pitcher" or position in {"P", "SP", "RP"}


def _player_supports_market(player: dict[str, Any], market: str) -> bool:
    if market in _HITTER_MARKETS:
        return _is_batter(player)
    if market in _PITCHER_MARKETS:
        return _is_pitcher(player) or _is_batter(player)
    return True


def _line_for_market(player_lines: Any, market: str) -> tuple[bool, Any]:
    if not isinstance(player_lines, dict) or market not in player_lines:
        return False, None
    line_val = player_lines[market]
    if isinstance(line_val, dict):
        line_val = line_val.get("line")
    if line_val is None:
        return False, None
    try:
        float(line_val)
    except (TypeError, ValueError):
        return False, None
    return True, line_val


def _attach_pick_provenance(
    scores: list[dict[str, Any]],
    match_inputs: dict[str, Any],
) -> list[dict[str, Any]]:
    for pick in scores:
        player = str(pick.get("player", ""))
        market = str(pick.get("market", ""))
        provenance = pick_input_provenance(match_inputs, player=player, market=market)
        if provenance:
            pick["input_provenance"] = provenance
        if provenance.get("player", {}).get("source") == "gemini_enriched" or provenance.get("line", {}).get("source") == "gemini_enriched":
            explainability = pick.setdefault("explainability", {})
            risk_flags = explainability.setdefault("risk_flags", [])
            if "gemini_enriched_input" not in risk_flags:
                risk_flags.append("gemini_enriched_input")
            root_risk_flags = pick.setdefault("risk_flags", [])
            if "gemini_enriched_input" not in root_risk_flags:
                root_risk_flags.append("gemini_enriched_input")
    return scores

