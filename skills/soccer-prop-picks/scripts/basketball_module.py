"""Basketball sport module with config-driven scoring.

Implements the SportModule protocol for basketball. Orchestrates LLM
providers (game context, player stats, prop lines) and feeds results
through the weighted-factor scoring engine.
"""

from __future__ import annotations

import logging
from typing import Any

from basketball_scoring import score_basketball_props
from missing_input_enrichment import (
    mark_enrichment_failed,
    merge_enriched_inputs,
    pick_input_provenance,
)

logger = logging.getLogger("colmillo.basketball")

_BASKETBALL_MARKETS = {
    "points", "rebounds", "assists", "threes",
    "steals", "blocks", "turnovers", "fantasy_score",
    "rebs_asts", "pra", "blks_stls",
    "fg_attempted", "fg_made", "two_pt_made",
}
_SCORING_MARKETS = (
    "points", "rebounds", "assists", "threes",
    "steals", "blocks", "turnovers",
    "fg_made", "fg_attempted", "two_pt_made",
    "rebs_asts", "pra", "blks_stls",
)
_MARKET_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "points": ("minutes_proj", "usage_rate", "points_avg", "points_last5"),
    "rebounds": ("minutes_proj", "usage_rate", "rebound_avg", "rebound_last5"),
    "assists": ("minutes_proj", "usage_rate", "assist_avg", "assist_last5"),
    "threes": ("minutes_proj", "usage_rate", "threes_avg", "threes_last5", "three_point_attempts"),
    "steals": ("minutes_proj", "usage_rate", "steals_avg", "steals_last5"),
    "blocks": ("minutes_proj", "usage_rate", "blocks_avg", "blocks_last5"),
    "turnovers": ("minutes_proj", "usage_rate", "turnovers_avg", "turnovers_last5"),
    "fg_made": ("minutes_proj", "usage_rate", "fg_made_avg", "fg_made_last5"),
    "fg_attempted": ("minutes_proj", "usage_rate", "fg_attempted_avg", "fg_attempted_last5"),
    "two_pt_made": ("minutes_proj", "usage_rate", "two_pt_made_avg", "two_pt_made_last5"),
    "rebs_asts": ("minutes_proj", "usage_rate", "rebound_avg", "assist_avg"),
    "pra": ("minutes_proj", "usage_rate", "points_avg", "rebound_avg", "assist_avg"),
    "blks_stls": ("minutes_proj", "usage_rate", "blocks_avg", "steals_avg"),
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


class BasketballDataQualityError(RuntimeError):
    """Raised when basketball inputs are too incomplete to produce picks."""

    def __init__(self, message: str, *, reason: str) -> None:
        self.reason = reason
        super().__init__(message)


class BasketballModule:
    def __init__(
        self,
        *,
        game_provider: Any | None = None,
        stats_provider: Any | None = None,
        props_provider: Any | None = None,
        enrichment_provider: Any | None = None,
        allow_deterministic_fallback: bool = False,
    ) -> None:
        self._game_provider = game_provider
        self._stats_provider = stats_provider
        self._props_provider = props_provider
        self._enrichment_provider = enrichment_provider
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

        if players is None and self._allow_fallback and self._enrichment_provider is None:
            players = list(_PLACEHOLDER_PLAYERS)
            lines = dict(_PLACEHOLDER_LINES)
            data_quality = {
                "source": "deterministic_fallback",
                "enrichment_status": "not_requested",
            }
        elif players is None and not self._allow_fallback:
            raise BasketballDataQualityError(
                "Could not find enough match details: no player data available for this game.",
                reason="no_player_data",
            )
        else:
            data_quality = {
                "source": "provider",
                "game_status": "ok" if game_ctx else "unavailable",
                "player_status": "ok" if players else "unavailable",
                "odds_status": "ok" if lines else "unavailable",
                "enrichment_status": "not_requested",
            }

        return {
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "league": league or "nba",
            "game": game_ctx or {},
            "players": players or [],
            "lines": lines or {},
            "data_quality": data_quality,
        }

    def score(
        self, match_inputs: dict[str, Any], *, markets: tuple[str, ...] = ()
    ) -> list[dict[str, Any]]:
        target_markets = set(markets) if markets else set(_SCORING_MARKETS)
        scoring_markets = tuple(m for m in target_markets if m in _SCORING_MARKETS)

        players = match_inputs.get("players", [])
        lines = match_inputs.get("lines", {})
        game = match_inputs.get("game", {})

        missing_inputs = _find_missing_basketball_inputs(players, lines, scoring_markets)
        if missing_inputs:
            self._attempt_enrichment(
                match_inputs=match_inputs,
                markets=scoring_markets,
                missing_fields=missing_inputs,
            )
            players = match_inputs.get("players", [])
            lines = match_inputs.get("lines", {})
            game = match_inputs.get("game", {})

        eligible, excluded_by_market = _partition_eligible_players(players, lines, scoring_markets)

        if excluded_by_market:
            _log_player_exclusions(match_inputs, scoring_markets, excluded_by_market)

        if scoring_markets and not eligible:
            missing_inputs = _find_missing_basketball_inputs(players, lines, scoring_markets)
            reason = "missing_prop_lines" if any(m.startswith("prop_line:") for m in missing_inputs) else "missing_player_context"
            _log_scoring_rejection(reason=reason, match_inputs=match_inputs, markets=scoring_markets, missing_fields=missing_inputs)
            raise BasketballDataQualityError(
                _basketball_missing_message(reason=reason),
                reason=reason,
            )

        player_dicts = self._build_scoring_dicts(eligible, lines, game, markets=scoring_markets)

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

        return _attach_pick_provenance(scores, match_inputs)

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
        except Exception as exc:
            logger.warning(
                "basketball_provider_error",
                extra={
                    "stage": "game",
                    "provider": type(self._game_provider).__name__,
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                    "error": str(exc),
                },
            )
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
        except Exception as exc:
            logger.warning(
                "basketball_provider_error",
                extra={
                    "stage": "player_stats",
                    "provider": type(self._stats_provider).__name__,
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                    "error": str(exc),
                },
            )
            return None

    def _fetch_prop_lines(
        self, players: list[dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        if self._props_provider is None or not players:
            return None
        try:
            return self._props_provider.get_prop_lines(
                players=players,
                markets=_SCORING_MARKETS,
            )
        except Exception as exc:
            logger.warning(
                "basketball_provider_error",
                extra={
                    "stage": "prop_lines",
                    "provider": type(self._props_provider).__name__,
                    "players_count": len(players) if players else 0,
                    "error": str(exc),
                },
            )
            return None

    def _attempt_enrichment(
        self,
        *,
        match_inputs: dict[str, Any],
        markets: tuple[str, ...],
        missing_fields: list[str],
    ) -> None:
        if self._enrichment_provider is None:
            return
        logger.info(
            "basketball_gemini_enrichment_attempt",
            extra={
                "sport": "basketball",
                "home_team": match_inputs.get("home_team", ""),
                "away_team": match_inputs.get("away_team", ""),
                "match_date": match_inputs.get("match_date", ""),
                "league": match_inputs.get("league", "nba"),
                "markets": ",".join(markets),
                "missing_fields": ",".join(missing_fields),
                "provider": type(self._enrichment_provider).__name__,
                "model": getattr(self._enrichment_provider, "model", "unknown"),
            },
        )
        try:
            enrichment, decision_metadata = self._run_best_of_n_enrichment(
                match_inputs=match_inputs, markets=markets, missing_fields=missing_fields
            )
        except Exception as exc:
            mark_enrichment_failed(match_inputs, reason=str(exc), missing_fields=missing_fields)
            logger.warning(
                "basketball_gemini_enrichment_failed",
                extra={
                    "sport": "basketball",
                    "home_team": match_inputs.get("home_team", ""),
                    "away_team": match_inputs.get("away_team", ""),
                    "match_date": match_inputs.get("match_date", ""),
                    "league": match_inputs.get("league", "nba"),
                    "markets": ",".join(markets),
                    "missing_fields": ",".join(missing_fields),
                    "provider": type(self._enrichment_provider).__name__,
                    "model": getattr(self._enrichment_provider, "model", "unknown"),
                    "error": str(exc),
                },
            )
            return

        if not enrichment:
            mark_enrichment_failed(match_inputs, reason="empty_enrichment", missing_fields=missing_fields)
            logger.warning(
                "basketball_gemini_enrichment_incomplete",
                extra={
                    "sport": "basketball",
                    "home_team": match_inputs.get("home_team", ""),
                    "away_team": match_inputs.get("away_team", ""),
                    "match_date": match_inputs.get("match_date", ""),
                    "league": match_inputs.get("league", "nba"),
                    "markets": ",".join(markets),
                    "missing_fields": ",".join(missing_fields),
                    "reason": "empty_enrichment",
                },
            )
            return

        merge_enriched_inputs(match_inputs, enrichment)
        data_quality = match_inputs.setdefault("data_quality", {})
        if isinstance(data_quality, dict) and decision_metadata:
            data_quality["enrichment_decision"] = decision_metadata
        logger.info(
            "basketball_gemini_enrichment_success",
            extra={
                "sport": "basketball",
                "home_team": match_inputs.get("home_team", ""),
                "away_team": match_inputs.get("away_team", ""),
                "match_date": match_inputs.get("match_date", ""),
                "league": match_inputs.get("league", "nba"),
                "markets": ",".join(markets),
                "missing_fields": ",".join(missing_fields),
                "enriched_players": len(enrichment.get("players", []) or []),
                "enriched_line_players": len(enrichment.get("lines", {}) or []),
                "enrichment_attempt_used": decision_metadata.get("winner_attempt") if decision_metadata else 1,
                "enrichment_temperature_used": decision_metadata.get("winner_temperature") if decision_metadata else None,
                "enrichment_selection_reason": decision_metadata.get("selection_reason") if decision_metadata else "single_shot",
                "enrichment_total_attempts": decision_metadata.get("n_attempts") if decision_metadata else 1,
            },
        )

    def _run_best_of_n_enrichment(
        self,
        *,
        match_inputs: dict[str, Any],
        markets: tuple[str, ...],
        missing_fields: list[str],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        common_kwargs: dict[str, Any] = {
            "sport": "basketball",
            "home_team": match_inputs.get("home_team", ""),
            "away_team": match_inputs.get("away_team", ""),
            "match_date": match_inputs.get("match_date", ""),
            "league": match_inputs.get("league", "nba"),
            "requested_markets": markets,
            "missing_fields": missing_fields,
            "players": [p for p in match_inputs.get("players", []) if isinstance(p, dict)],
            "lines": match_inputs.get("lines", {}),
            "game": match_inputs.get("game", {}),
            "official_context": match_inputs.get("data_quality", {}),
        }
        if hasattr(self._enrichment_provider, "enrich_missing_inputs_best_of_n"):
            return self._enrichment_provider.enrich_missing_inputs_best_of_n(
                **common_kwargs,
                required_fields_map=_MARKET_REQUIRED_FIELDS,
            )
        return self._enrichment_provider.enrich_missing_inputs(**common_kwargs), None

    @staticmethod
    def _build_scoring_dicts(
        players: list[dict[str, Any]],
        lines: dict[str, Any],
        game: dict[str, Any],
        *,
        markets: tuple[str, ...] = _SCORING_MARKETS,
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

            for market in markets:
                line_key = f"line_{market}"
                if line_key not in d:
                    required = _MARKET_REQUIRED_FIELDS.get(market, ())
                    if any(player.get(f) is None for f in required):
                        continue
                    market_data = player_lines.get(market, {})
                    if isinstance(market_data, dict):
                        if market_data.get("line") is not None:
                            d[line_key] = market_data.get("line")
                        if market_data.get("market_agreement") is not None:
                            d["market_agreement"] = market_data["market_agreement"]
                    elif isinstance(market_data, (int, float)):
                        d[line_key] = market_data

            dicts.append(d)
        return dicts


def _find_missing_basketball_inputs(
    players: Any,
    lines: Any,
    markets: tuple[str, ...],
) -> list[str]:
    player_list = [p for p in players if isinstance(p, dict)] if isinstance(players, list) else []
    if not player_list:
        return ["players"]

    missing: list[str] = []
    for player in player_list:
        name = str(player.get("player_name", "")).strip() or "Unknown"
        for market in markets:
            for field in _MARKET_REQUIRED_FIELDS.get(market, ()):
                if player.get(field) is None:
                    missing.append(f"player:{name}:{field}")
            player_lines = lines.get(name, {}) if isinstance(lines, dict) else {}
            has_line, _ = _line_for_market(player_lines, market)
            if not has_line:
                missing.append(f"prop_line:{name}:{market}")
    return missing


def _partition_eligible_players(
    players: list[dict[str, Any]],
    lines: Any,
    markets: tuple[str, ...],
) -> tuple[list[dict[str, Any]], dict[str, list[tuple[str, list[str]]]]]:
    """Partition players into eligible vs excluded per market.

    Returns (eligible_players, excluded_by_market) where eligible_players
    contains players with complete data for at least one requested market.
    """
    eligible_names: set[str] = set()
    excluded_by_market: dict[str, list[tuple[str, list[str]]]] = {}

    for market in markets:
        excluded_by_market[market] = []
        required = _MARKET_REQUIRED_FIELDS.get(market, ())
        for player in players:
            name = str(player.get("player_name", "")).strip() or "Unknown"
            missing_fields: list[str] = []
            for field in required:
                if player.get(field) is None:
                    missing_fields.append(field)
            player_lines = lines.get(name, {}) if isinstance(lines, dict) else {}
            has_line, _ = _line_for_market(player_lines, market)
            if not has_line:
                missing_fields.append(f"line_{market}")
            if missing_fields:
                excluded_by_market[market].append((name, missing_fields))
            else:
                eligible_names.add(name)

    excluded_by_market = {m: entries for m, entries in excluded_by_market.items() if entries}
    eligible = [p for p in players if str(p.get("player_name", "")).strip() in eligible_names]
    return eligible, excluded_by_market


def _log_player_exclusions(
    match_inputs: dict[str, Any],
    markets: tuple[str, ...],
    excluded_by_market: dict[str, list[tuple[str, list[str]]]],
) -> None:
    all_excluded_names: set[str] = set()
    for entries in excluded_by_market.values():
        for name, _ in entries:
            all_excluded_names.add(name)

    logger.info(
        "basketball_players_excluded sport=basketball home_team=%s away_team=%s "
        "match_date=%s league=%s markets=%s excluded_count=%s excluded_players=%s",
        match_inputs.get("home_team", ""),
        match_inputs.get("away_team", ""),
        match_inputs.get("match_date", ""),
        match_inputs.get("league", "nba"),
        ",".join(markets),
        len(all_excluded_names),
        ",".join(sorted(all_excluded_names)[:10]),
    )

    data_quality = match_inputs.setdefault("data_quality", {})
    if isinstance(data_quality, dict):
        data_quality["excluded_players"] = {
            market: [name for name, _ in entries]
            for market, entries in excluded_by_market.items()
        }


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


def _basketball_missing_message(*, reason: str) -> str:
    if reason == "missing_prop_lines":
        return "Could not find enough match details: missing prop lines for requested basketball markets."
    return "Could not find enough match details: missing basketball player context for requested markets."


def _log_scoring_rejection(
    *,
    reason: str,
    match_inputs: dict[str, Any],
    markets: tuple[str, ...],
    missing_fields: list[str],
) -> None:
    logger.warning(
        "basketball_scoring_rejected reason=%s sport=basketball home_team=%s away_team=%s "
        "match_date=%s league=%s markets=%s players=%s prop_line_players=%s missing_fields=%s "
        "enrichment_status=%s",
        reason,
        match_inputs.get("home_team", ""),
        match_inputs.get("away_team", ""),
        match_inputs.get("match_date", ""),
        match_inputs.get("league", "nba"),
        ",".join(markets),
        len(match_inputs.get("players", []) or []),
        len(match_inputs.get("lines", {}) or {}),
        ",".join(missing_fields[:20]),
        match_inputs.get("data_quality", {}).get("enrichment_status", "unknown"),
    )


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
    return scores
