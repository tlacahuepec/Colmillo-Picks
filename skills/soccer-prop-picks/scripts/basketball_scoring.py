"""Basketball config-driven prop scoring engine.

Weighted-factor scorer for NBA player props. Loads factor weights from
config.basketball_scoring_weights.json and computes per-market scores
using basketball-specific factors (minutes, usage, pace, matchups, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.basketball_scoring_weights.json"

_FACTOR_DISPATCH: dict[str, str] = {
    "minutes_rotation_risk": "_compute_minutes_rotation_risk",
    "usage_rate_opportunity": "_compute_usage_rate_opportunity",
    "position_rebound_opportunity": "_compute_position_score",
    "position_playmaking_role": "_compute_position_score",
    "three_point_volume": "_compute_three_point_volume",
    "pace_tempo": "_compute_pace_tempo",
    "opp_defensive_rating": "_compute_opp_defensive_rating",
    "recent_form_momentum": "_compute_recent_form_momentum",
    "rest_days_b2b": "_compute_rest_days",
    "home_away_adjustment": "_compute_home_away",
    "teammate_absence_usage": "_compute_teammate_absence",
    "market_agreement": "_compute_market_agreement",
}

_MARKET_STAT_KEYS: dict[str, tuple[str, str, str]] = {
    "points": ("points_avg", "points_last5", "opp_points_rank"),
    "rebounds": ("rebound_avg", "rebound_last5", "opp_rebound_rank"),
    "assists": ("assist_avg", "assist_last5", "opp_assist_rank"),
    "threes": ("threes_avg", "threes_last5", "opp_three_rank"),
    "steals": ("steals_avg", "steals_last5", "opp_steals_rank"),
    "blocks": ("blocks_avg", "blocks_last5", "opp_blocks_rank"),
    "turnovers": ("turnovers_avg", "turnovers_last5", "opp_turnovers_rank"),
    "fg_made": ("fg_made_avg", "fg_made_last5", "opp_fg_rank"),
    "fg_attempted": ("fg_attempted_avg", "fg_attempted_last5", "opp_fg_rank"),
    "two_pt_made": ("two_pt_made_avg", "two_pt_made_last5", "opp_fg_rank"),
}

_COMBO_MARKET_COMPONENTS: dict[str, tuple[str, ...]] = {
    "rebs_asts": ("rebounds", "assists"),
    "pra": ("points", "rebounds", "assists"),
    "blks_stls": ("blocks", "steals"),
}


def score_basketball_props(
    players: list[dict[str, Any]],
    *,
    markets: tuple[str, ...] = ("points", "rebounds", "assists", "threes"),
) -> list[dict[str, Any]]:
    config = _load_config()
    results: list[dict[str, Any]] = []
    for player in players:
        for market in markets:
            pick = _score_market_candidate(player, market, config)
            if pick is not None:
                results.append(pick)
    return results


def _load_config(config_path: str | None = None) -> dict[str, Any]:
    path = Path(config_path).resolve() if config_path else _CONFIG_PATH
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _clip(value: float) -> float:
    return min(1.0, max(0.0, value))


def _score_market_candidate(
    player: dict[str, Any], market: str, config: dict[str, Any]
) -> dict[str, Any] | None:
    market_config = config.get(market)
    if market_config is None:
        return None

    name = player.get("player_name", "Unknown")
    weights = market_config["factor_weights"]
    calibration = config.get("calibration", {})
    risk_flags: list[str] = []

    has_missing = _check_missing_data(player, market)
    if has_missing:
        risk_flags.append("missing_data")

    factors: list[dict[str, Any]] = []
    overall_score = 0.0

    for factor_name, weight in weights.items():
        raw_score = _compute_factor(factor_name, player, market, market_config, calibration)
        clipped = _clip(raw_score)
        weighted = clipped * weight
        overall_score += weighted
        factors.append({
            "factor": factor_name,
            "score": round(clipped, 4),
            "weight": weight,
        })

    overall_score = _clip(overall_score)
    factors.sort(key=lambda f: f["score"] * f["weight"], reverse=True)

    thresholds = calibration.get("confidence_thresholds", {"high": 0.76, "medium": 0.60})
    confidence = _determine_confidence(overall_score, risk_flags, thresholds)

    line = player.get(f"line_{market}")
    if not line:
        return None
    direction = _resolve_direction(player, market, line)

    return {
        "player": name,
        "market": market,
        "line": line,
        "direction": direction,
        "score": round(overall_score, 4),
        "confidence": confidence,
        "explainability": {
            "risk_flags": risk_flags,
            "top_contributing_factors": factors[:5],
        },
    }


def _check_missing_data(player: dict[str, Any], market: str) -> bool:
    critical = ["minutes_proj", "usage_rate"]
    combo = _COMBO_MARKET_COMPONENTS.get(market)
    if combo:
        for component in combo:
            stat_keys = _MARKET_STAT_KEYS.get(component, ())
            if stat_keys:
                critical.append(stat_keys[0])
    else:
        stat_keys = _MARKET_STAT_KEYS.get(market, ())
        if stat_keys:
            critical.append(stat_keys[0])
    return any(player.get(k) is None for k in critical)


def _compute_factor(
    factor_name: str,
    player: dict[str, Any],
    market: str,
    market_config: dict[str, Any],
    calibration: dict[str, Any],
) -> float:
    if factor_name == "minutes_rotation_risk":
        return _compute_minutes_rotation_risk(player, calibration)
    elif factor_name == "usage_rate_opportunity":
        return _compute_usage_rate_opportunity(player)
    elif factor_name in ("position_rebound_opportunity", "position_playmaking_role"):
        return _compute_position_score(player, market_config)
    elif factor_name == "three_point_volume":
        return _compute_three_point_volume(player)
    elif factor_name == "pace_tempo":
        return _compute_pace_tempo(player, calibration)
    elif factor_name == "opp_defensive_rating":
        return _compute_opp_defensive_rating(player, market)
    elif factor_name == "recent_form_momentum":
        return _compute_recent_form_momentum(player, market)
    elif factor_name == "rest_days_b2b":
        return _compute_rest_days(player, calibration)
    elif factor_name == "home_away_adjustment":
        return _compute_home_away(player, calibration)
    elif factor_name == "teammate_absence_usage":
        return _compute_teammate_absence(player)
    elif factor_name == "market_agreement":
        return _compute_market_agreement(player)
    return 0.5


def _compute_minutes_rotation_risk(player: dict[str, Any], calibration: dict[str, Any]) -> float:
    minutes = player.get("minutes_proj")
    if minutes is None:
        return 0.4
    base = minutes / 48.0
    rotation = player.get("rotation_risk", "normal")
    multipliers = calibration.get("rotation_risk", {})
    mult = multipliers.get(rotation, 0.88)
    return base * mult


def _compute_usage_rate_opportunity(player: dict[str, Any]) -> float:
    usage = player.get("usage_rate")
    if usage is None:
        return 0.5
    return _clip(usage / 0.35)


def _compute_position_score(player: dict[str, Any], market_config: dict[str, Any]) -> float:
    position = player.get("position", "SF")
    scores = market_config.get("position_scores", {})
    return scores.get(position, 0.5)


def _compute_three_point_volume(player: dict[str, Any]) -> float:
    attempts = player.get("three_point_attempts")
    if attempts is not None:
        return _clip(attempts / 10.0)
    avg = player.get("threes_avg")
    if avg is not None:
        return _clip(avg / 5.0)
    return 0.4


def _compute_pace_tempo(player: dict[str, Any], calibration: dict[str, Any]) -> float:
    pace = player.get("pace_factor")
    if pace is None:
        return 0.5
    tiers = calibration.get("pace_tiers", {})
    for tier_name in ("very_fast", "fast", "average", "slow", "very_slow"):
        tier = tiers.get(tier_name)
        if tier and pace >= tier["min"]:
            return tier["score"] / 1.0
    return 0.5


def _compute_opp_defensive_rating(player: dict[str, Any], market: str) -> float:
    stat_keys = _MARKET_STAT_KEYS.get(market)
    if stat_keys is None:
        return 0.5
    rank_key = stat_keys[2]
    rank = player.get(rank_key)
    if rank is None:
        return 0.5
    return _clip(rank / 30.0)


def _compute_recent_form_momentum(player: dict[str, Any], market: str) -> float:
    stat_keys = _MARKET_STAT_KEYS.get(market)
    if stat_keys is None:
        return 0.5
    avg_key, last5_key = stat_keys[0], stat_keys[1]
    avg = player.get(avg_key)
    last5 = player.get(last5_key)
    if avg is None or last5 is None or avg <= 0:
        return 0.5
    trend = (last5 - avg) / avg
    return _clip(0.5 + trend)


def _compute_rest_days(player: dict[str, Any], calibration: dict[str, Any]) -> float:
    rest = player.get("rest_days")
    if rest is None:
        return 0.5
    rest_config = calibration.get("rest_days", {})
    if rest == 0:
        adj = rest_config.get("0", -0.12)
    elif rest == 1:
        adj = rest_config.get("1", 0.0)
    elif rest == 2:
        adj = rest_config.get("2", 0.06)
    else:
        adj = rest_config.get("3_plus", 0.08)
    return _clip(0.5 + adj)


def _compute_home_away(player: dict[str, Any], calibration: dict[str, Any]) -> float:
    ha = player.get("home_away")
    if ha is None:
        return 0.5
    ha_config = calibration.get("home_away", {})
    if ha == "home":
        return _clip(0.5 + ha_config.get("home_bonus", 0.06))
    return _clip(0.5 - ha_config.get("away_penalty", 0.04))


def _compute_teammate_absence(player: dict[str, Any]) -> float:
    boost = player.get("usage_boost")
    if boost is None:
        return 0.5
    return _clip(0.5 + boost)


def _compute_market_agreement(player: dict[str, Any]) -> float:
    agreement = player.get("market_agreement")
    if agreement is None:
        return 0.5
    return _clip(agreement)


def _determine_confidence(
    score: float, risk_flags: list[str], thresholds: dict[str, float]
) -> str:
    if "missing_data" in risk_flags:
        return "low"
    if score >= thresholds.get("high", 0.76):
        return "high"
    if score >= thresholds.get("medium", 0.60):
        return "medium"
    return "low"


def _resolve_direction(player: dict[str, Any], market: str, line: float) -> str:
    combo = _COMBO_MARKET_COMPONENTS.get(market)
    if combo:
        projected = 0.0
        for component in combo:
            stat_keys = _MARKET_STAT_KEYS.get(component)
            if stat_keys is None:
                continue
            avg_key, last5_key = stat_keys[0], stat_keys[1]
            avg = player.get(avg_key)
            last5 = player.get(last5_key)
            projected += (last5 if last5 is not None else avg) if avg is not None else 0.0
        return "over" if projected >= line else "under"

    stat_keys = _MARKET_STAT_KEYS.get(market)
    if stat_keys is None:
        return "over"
    avg_key, last5_key = stat_keys[0], stat_keys[1]
    avg = player.get(avg_key)
    last5 = player.get(last5_key)
    if avg is None:
        return "over"
    projected = last5 if last5 is not None else avg
    if projected >= line:
        return "over"
    return "under"
