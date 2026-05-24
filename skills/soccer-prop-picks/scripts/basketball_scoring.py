"""Basketball core prop scoring.

First-pass scoring for basketball player props using basketball-specific
factors: minutes projection, usage rate, recent form, pace, and opponent
context. Missing optional data adds risk flags instead of crashing.
"""

from __future__ import annotations

from typing import Any


def score_basketball_props(
    players: list[dict[str, Any]],
    *,
    markets: tuple[str, ...] = ("points", "rebounds", "assists", "threes"),
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for player in players:
        for market in markets:
            pick = _score_single(player, market)
            if pick is not None:
                results.append(pick)
    return results


def _score_single(player: dict[str, Any], market: str) -> dict[str, Any] | None:
    name = player.get("player_name", "Unknown")
    scorer = _MARKET_SCORERS.get(market)
    if scorer is None:
        return None
    raw_score, risk_flags = scorer(player)
    confidence = _determine_confidence(raw_score, risk_flags)
    line = player.get(f"line_{market}", 0)

    return {
        "player": name,
        "market": market,
        "line": line,
        "direction": "over" if raw_score >= 0.5 else "under",
        "score": round(min(1.0, max(0.0, raw_score)), 4),
        "confidence": confidence,
        "explainability": {"risk_flags": risk_flags},
    }


def _score_points(player: dict[str, Any]) -> tuple[float, list[str]]:
    risk_flags: list[str] = []
    minutes = player.get("minutes_proj")
    usage = player.get("usage_rate")
    avg = player.get("points_avg")
    last5 = player.get("points_last5")
    pace = player.get("pace_factor")

    if minutes is None or usage is None:
        risk_flags.append("missing_data")
        return 0.45, risk_flags

    base = 0.5
    minutes_factor = (minutes - 30) * 0.008
    usage_factor = (usage - 0.25) * 1.5
    form_factor = 0.0
    if avg is not None and last5 is not None and avg > 0:
        form_factor = (last5 - avg) / avg * 0.3
    pace_factor = 0.0
    if pace is not None:
        pace_factor = (pace - 1.0) * 0.5

    score = base + minutes_factor + usage_factor + form_factor + pace_factor
    return score, risk_flags


def _score_assists(player: dict[str, Any]) -> tuple[float, list[str]]:
    risk_flags: list[str] = []
    avg = player.get("assist_avg")
    last5 = player.get("assist_last5")
    position = player.get("position", "")

    if avg is None:
        risk_flags.append("missing_data")
        return 0.45, risk_flags

    base = 0.5
    role_factor = 0.0
    if position in ("PG", "SG"):
        role_factor = 0.08
    elif position in ("C", "PF"):
        role_factor = -0.05

    volume_factor = (avg - 5.0) * 0.03

    trend_factor = 0.0
    if last5 is not None and avg > 0:
        trend_factor = (last5 - avg) / avg * 0.25

    score = base + role_factor + volume_factor + trend_factor
    return score, risk_flags


def _score_rebounds(player: dict[str, Any]) -> tuple[float, list[str]]:
    risk_flags: list[str] = []
    avg = player.get("rebound_avg")
    minutes = player.get("minutes_proj")
    opp_rank = player.get("opp_rebound_rank")

    if avg is None:
        risk_flags.append("missing_data")
        return 0.45, risk_flags

    base = 0.5
    minutes_factor = 0.0
    if minutes is not None:
        minutes_factor = (minutes - 30) * 0.006

    volume_factor = (avg - 7.0) * 0.02

    matchup_factor = 0.0
    if opp_rank is not None:
        matchup_factor = (opp_rank - 15) * 0.005

    score = base + minutes_factor + volume_factor + matchup_factor
    return score, risk_flags


def _score_threes(player: dict[str, Any]) -> tuple[float, list[str]]:
    risk_flags: list[str] = []
    avg = player.get("threes_avg")
    last5 = player.get("threes_last5")

    if avg is None:
        risk_flags.append("missing_data")
        return 0.45, risk_flags

    base = 0.5
    volume_factor = (avg - 2.5) * 0.04

    trend_factor = 0.0
    if last5 is not None and avg > 0:
        trend_factor = (last5 - avg) / avg * 0.2

    score = base + volume_factor + trend_factor
    return score, risk_flags


def _determine_confidence(score: float, risk_flags: list[str]) -> str:
    if "missing_data" in risk_flags:
        return "low"
    if abs(score - 0.5) > 0.15:
        return "high"
    if abs(score - 0.5) > 0.07:
        return "medium"
    return "low"


_MARKET_SCORERS = {
    "points": _score_points,
    "assists": _score_assists,
    "rebounds": _score_rebounds,
    "threes": _score_threes,
}
