"""Baseball config-driven prop scoring engine.

Weighted-factor scorer for MLB player props. Loads factor weights from
config.baseball_scoring_weights.json and computes per-market scores
using baseball-specific factors (lineup position, pitcher matchup,
ballpark, weather, recent form, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.baseball_scoring_weights.json"

_FACTOR_DISPATCH: dict[str, str] = {
    "lineup_position_opportunity": "_compute_lineup_position",
    "pitcher_matchup_handedness": "_compute_pitcher_matchup",
    "recent_form_momentum": "_compute_recent_form",
    "ballpark_factor": "_compute_ballpark",
    "weather_impact": "_compute_weather",
    "team_run_expectancy": "_compute_team_run_expectancy",
    "rest_days": "_compute_rest_days",
    "home_away_adjustment": "_compute_home_away",
    "opp_team_contact_rate": "_compute_opp_contact",
    "workload_durability": "_compute_workload",
    "market_agreement": "_compute_market_agreement",
}

_MARKET_STAT_KEYS: dict[str, tuple[str, str]] = {
    "hits": ("hits_per_game", "hits_last5_per_game"),
    "total_bases": ("tb_per_game", "tb_last5_per_game"),
    "runs": ("runs_per_game", "runs_last5_per_game"),
    "rbi": ("rbi_per_game", "rbi_last5_per_game"),
    "home_runs": ("hr_per_game", "hr_last5_per_game"),
    "walks": ("bb_per_game", "bb_last5_per_game"),
    "strikeouts": ("k_per_game", "k_last5_per_game"),
    "pitcher_outs": ("outs_per_game", "outs_last5_per_game"),
}


def score_baseball_props(
    players: list[dict[str, Any]],
    *,
    markets: tuple[str, ...] = (
        "hits", "total_bases", "runs", "rbi",
        "home_runs", "strikeouts", "walks", "pitcher_outs",
    ),
    config_path: str | None = None,
) -> list[dict[str, Any]]:
    config = _load_config(config_path=config_path)
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
    weights = market_config.get("factor_weights", {})
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

    line_key = f"line_{market}"
    line = player.get(line_key)
    if not line:
        return None
    direction = _resolve_direction(player, market, line)

    top_k = config.get("global", {}).get("top_k", 5)

    return {
        "player": name,
        "market": market,
        "line": line,
        "direction": direction,
        "score": round(overall_score, 4),
        "confidence": confidence,
        "explainability": {
            "risk_flags": risk_flags,
            "top_contributing_factors": factors[:top_k],
        },
    }


def _check_missing_data(player: dict[str, Any], market: str) -> bool:
    stat_keys = _MARKET_STAT_KEYS.get(market)
    if not stat_keys:
        return False
    avg_key = stat_keys[0]
    critical = [avg_key]
    player_type = player.get("player_type", "batter")
    if player_type == "batter":
        critical.append("batting_order")
    return any(player.get(k) is None for k in critical)


def _compute_factor(
    factor_name: str,
    player: dict[str, Any],
    market: str,
    market_config: dict[str, Any],
    calibration: dict[str, Any],
) -> float:
    if factor_name == "lineup_position_opportunity":
        return _compute_lineup_position(player, market_config)
    elif factor_name == "pitcher_matchup_handedness":
        return _compute_pitcher_matchup(player, calibration)
    elif factor_name == "recent_form_momentum":
        return _compute_recent_form(player, market)
    elif factor_name == "ballpark_factor":
        return _compute_ballpark(player, market)
    elif factor_name == "weather_impact":
        return _compute_weather(player, calibration)
    elif factor_name == "team_run_expectancy":
        return _compute_team_run_expectancy(player)
    elif factor_name == "rest_days":
        return _compute_rest_days(player, calibration)
    elif factor_name == "home_away_adjustment":
        return _compute_home_away(player, calibration)
    elif factor_name == "opp_team_contact_rate":
        return _compute_opp_contact(player)
    elif factor_name == "workload_durability":
        return _compute_workload(player)
    elif factor_name == "market_agreement":
        return _compute_market_agreement(player)
    return 0.5


def _compute_lineup_position(player: dict[str, Any], market_config: dict[str, Any]) -> float:
    order = player.get("batting_order")
    if order is None:
        return 0.5
    scores = market_config.get("position_scores", {})
    return scores.get(str(order), 0.5)


def _compute_pitcher_matchup(player: dict[str, Any], calibration: dict[str, Any]) -> float:
    batter_hand = player.get("handedness")
    pitcher_hand = player.get("opposing_pitcher_hand")
    if batter_hand is None or pitcher_hand is None:
        return 0.5
    splits = calibration.get("handedness_splits", {})
    if batter_hand != pitcher_hand:
        adj = splits.get("platoon_advantage", 0.12)
    else:
        adj = splits.get("same_hand_penalty", -0.06)
    return _clip(0.5 + adj)


def _compute_recent_form(player: dict[str, Any], market: str) -> float:
    stat_keys = _MARKET_STAT_KEYS.get(market)
    if stat_keys is None:
        return 0.5
    avg_key, last5_key = stat_keys
    avg = player.get(avg_key)
    last5 = player.get(last5_key)
    if avg is None or last5 is None or avg <= 0:
        return 0.5
    trend = (last5 - avg) / avg
    return _clip(0.5 + trend)


def _compute_ballpark(player: dict[str, Any], market: str) -> float:
    if market == "home_runs":
        factor = player.get("hr_factor")
        if factor is not None:
            return _clip(factor)
    factor = player.get("park_factor")
    if factor is None:
        return 0.5
    return _clip(factor)


def _compute_weather(player: dict[str, Any], calibration: dict[str, Any]) -> float:
    temp = player.get("temp_f")
    if temp is None:
        return 0.5
    tiers = calibration.get("weather_tiers", {})
    base_score = 0.5
    for tier_name in ("hot", "warm", "mild", "cold"):
        tier = tiers.get(tier_name)
        if tier and temp >= tier["min_temp"]:
            base_score = tier["score"]
            break

    wind_dir = player.get("wind_direction")
    wind_adj_config = calibration.get("wind_direction", {})
    wind_adj = 0.0
    if wind_dir is not None:
        wind_dir_lower = wind_dir.lower()
        if "out" in wind_dir_lower:
            wind_adj = wind_adj_config.get("out", 0.12)
        elif "in" in wind_dir_lower:
            wind_adj = wind_adj_config.get("in", -0.10)
        else:
            wind_adj = wind_adj_config.get("cross", 0.0)

    return _clip(base_score + wind_adj)


def _compute_team_run_expectancy(player: dict[str, Any]) -> float:
    implied = player.get("team_implied_total")
    if implied is None:
        return 0.5
    return _clip(implied / 6.0)


def _compute_rest_days(player: dict[str, Any], calibration: dict[str, Any]) -> float:
    rest = player.get("days_rest")
    if rest is None:
        return 0.5
    rest_config = calibration.get("rest_days", {})
    if rest <= 3:
        adj = rest_config.get("3_less", -0.10)
    elif rest == 4:
        adj = rest_config.get("4", 0.0)
    else:
        adj = rest_config.get("5_plus", 0.06)
    return _clip(0.5 + adj)


def _compute_home_away(player: dict[str, Any], calibration: dict[str, Any]) -> float:
    ha = player.get("home_away")
    if ha is None:
        return 0.5
    ha_config = calibration.get("home_away", {})
    if ha == "home":
        return _clip(0.5 + ha_config.get("home_bonus", 0.05))
    return _clip(0.5 - ha_config.get("away_penalty", 0.03))


def _compute_opp_contact(player: dict[str, Any]) -> float:
    opp_k_rate = player.get("opp_k_rate")
    if opp_k_rate is None:
        return 0.5
    return _clip(1.0 - opp_k_rate)


def _compute_workload(player: dict[str, Any]) -> float:
    recent = player.get("recent_innings")
    max_innings = player.get("max_innings")
    if recent is None or max_innings is None or max_innings <= 0:
        return 0.5
    return _clip(1.0 - recent / max_innings)


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
    stat_keys = _MARKET_STAT_KEYS.get(market)
    if stat_keys is None:
        return "over"
    avg_key, last5_key = stat_keys
    avg = player.get(avg_key)
    last5 = player.get(last5_key)
    if avg is None:
        return "over"
    projected = last5 if last5 is not None else avg
    if projected >= line:
        return "over"
    return "under"
