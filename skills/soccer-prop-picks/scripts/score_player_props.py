#!/usr/bin/env python3
"""Score soccer player pass/shot props using configurable deterministic heuristics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.scoring_weights.json"


def _clip(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _parse_utc_timestamp(raw_value: Any) -> datetime | None:
    if not raw_value:
        return None
    value = str(raw_value).strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)




def _normalize_probability(raw_value: Any, default: float = 0.5) -> float:
    if raw_value is None:
        return default

    if isinstance(raw_value, str):
        value = raw_value.strip()
        if not value:
            return default
        is_pct = value.endswith("%")
        if is_pct:
            value = value[:-1].strip()
        try:
            parsed = float(value)
        except ValueError:
            return default
        if is_pct or parsed > 1.0:
            parsed /= 100.0
        return _clip(parsed)

    try:
        parsed = float(raw_value)
    except (TypeError, ValueError):
        return default

    if parsed > 1.0:
        parsed /= 100.0
    return _clip(parsed)


def _normalize_last_5_result(result: Any) -> str | None:
    if isinstance(result, dict):
        for key in ("result", "outcome", "value"):
            if key in result:
                result = result[key]
                break

    token = str(result).strip().upper()
    if not token:
        return None

    aliases = {
        "W": "W",
        "WIN": "W",
        "WON": "W",
        "3": "W",
        "D": "D",
        "DRAW": "D",
        "T": "D",
        "1": "D",
        "L": "L",
        "LOSS": "L",
        "LOST": "L",
        "0": "L",
    }
    return aliases.get(token)

def _degrade_confidence(confidence: str) -> str:
    ladder = {"high": "medium", "medium": "low", "low": "low"}
    return ladder.get(confidence, "low")


def _required_freshness_timestamps(match_inputs: dict[str, Any]) -> dict[str, Any]:
    teams = match_inputs.get("teams", [])
    home = next((team for team in teams if team.get("home_away") == "home"), teams[0] if teams else {})
    away = next((team for team in teams if team.get("home_away") == "away"), teams[1] if len(teams) > 1 else {})
    return {
        "home_lineup_timestamp_utc": home.get("projected_lineup", {}).get("source_timestamp_utc"),
        "away_lineup_timestamp_utc": away.get("projected_lineup", {}).get("source_timestamp_utc"),
        "odds_timestamp_utc": match_inputs.get("market", {}).get("source_timestamp_utc"),
        "weather_timestamp_utc": match_inputs.get("match", {}).get("weather", {}).get("source_timestamp_utc"),
    }


def _evaluate_guardrails(match_inputs: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    market_cfg = cfg.get("global", {}).get("market_freshness", {})
    max_odds_age_minutes = int(market_cfg.get("max_odds_age_minutes", 30))
    missing_fields: list[str] = []
    blocking_warnings: list[str] = []

    required_timestamps = _required_freshness_timestamps(match_inputs)
    for field_name, raw_value in required_timestamps.items():
        if _parse_utc_timestamp(raw_value) is None:
            missing_fields.append(field_name)

    teams = match_inputs.get("teams", [])
    for team in teams:
        lineup_status = str(team.get("projected_lineup", {}).get("status", "unknown")).lower()
        if lineup_status != "confirmed":
            team_name = str(team.get("team_name") or team.get("team_id") or "unknown_team")
            blocking_warnings.append(f"lineup_unconfirmed:{team_name}")

    odds_timestamp = _parse_utc_timestamp(required_timestamps.get("odds_timestamp_utc"))
    if odds_timestamp is not None:
        age_minutes = (now_utc - odds_timestamp).total_seconds() / 60.0
        if age_minutes > max_odds_age_minutes:
            blocking_warnings.append(f"odds_stale:{age_minutes:.1f}m_old")

    return {
        "required_timestamps": required_timestamps,
        "blocking_warnings": sorted(set(blocking_warnings)),
        "missing_freshness_timestamps": missing_fields,
    }


def _load_config(config_path: str | None = None) -> dict[str, Any]:
    path = Path(config_path).resolve() if config_path else CONFIG_PATH
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_role(player: dict[str, Any]) -> str:
    return str(player.get("role_tag") or player.get("specific_role") or player.get("position_group") or "MID").upper()


def _team_index(match_inputs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    teams = match_inputs.get("teams", [])
    return {team.get("team_id"): team for team in teams if team.get("team_id")}


def _market_agreement(player: dict[str, Any], market_block: dict[str, Any]) -> tuple[float, list[str]]:
    snapshots = player.get("market", {}).get("sportsbook_snapshots") or market_block.get("sportsbook_snapshots") or []
    if not snapshots:
        return 0.5, ["missing_market_sources"]

    odds = [float(s.get("odds_decimal", 0)) for s in snapshots if s.get("odds_decimal")]
    if len(odds) < 2:
        return 0.5, ["insufficient_market_sources"]

    spread = max(odds) - min(odds)
    # tight spread is stronger agreement. spread ~0.01 => ~0.98 score, spread >=0.35 => 0
    agreement = _clip(1.0 - (spread / 0.35))
    flags: list[str] = []
    if len(odds) < 5:
        flags.append("less_than_5_odds_sources")
    if spread > 0.25:
        flags.append("market_disagreement")
    return agreement, flags


def _minutes_sub_score(player: dict[str, Any], cfg: dict[str, Any]) -> tuple[float, list[str]]:
    expected_minutes = float(player.get("expected_minutes", 0.0))
    minutes_score = _clip(expected_minutes / 95.0)

    sub_risk = str(player.get("substitution_risk", "medium")).lower()
    sub_multiplier = cfg["calibration"]["substitution_risk"].get(sub_risk, 0.78)
    score = _clip(minutes_score * sub_multiplier)

    flags: list[str] = []
    if expected_minutes < 65:
        flags.append("low_expected_minutes")
    if sub_risk == "high":
        flags.append("high_substitution_risk")
    return score, flags


def _role_score(player: dict[str, Any], market_type: str, cfg: dict[str, Any]) -> tuple[float, list[str]]:
    role = _resolve_role(player)
    role_scores = cfg[market_type]["role_scores"]
    score = role_scores.get(role, role_scores.get(player.get("position_group", "MID"), 0.5))

    flags: list[str] = []
    if market_type == "passes" and role in {"ST", "CF", "FWD"}:
        flags.append("attacker_role_for_passes")

    if market_type == "shots":
        is_lone_striker = bool(player.get("is_lone_striker", False))
        if is_lone_striker:
            score = _clip(score + float(cfg["shots"]["lone_striker_bonus"]))
        if role in {"CB", "DM", "GK", "DEF"}:
            flags.append("deep_role_for_shots")

    return float(score), flags


def _possession_opponent_style_score(
    team: dict[str, Any], opponent: dict[str, Any], cfg: dict[str, Any]
) -> tuple[float, list[str]]:
    own_possession = float(team.get("possession_profile", {}).get("avg_possession_pct", 50.0))
    own_score = _clip(own_possession / 100.0)

    opp_style = opponent.get("possession_profile", {}).get("style_tag", "balanced")
    style_impact = float(cfg["calibration"]["opponent_style_impact"].get(opp_style, 0.0))
    score = _clip(own_score + style_impact)

    flags: list[str] = []
    if own_possession < 44:
        flags.append("low_team_possession")
    if opp_style == "high_possession":
        flags.append("opponent_controls_ball")
    return score, flags


def _match_state_score(match: dict[str, Any], team: dict[str, Any], cfg: dict[str, Any]) -> tuple[float, list[str]]:
    motivation = team.get("standings_context", {}).get("motivation_tag", "midtable")
    motivation_bonus = float(cfg["calibration"]["motivation_bonus"].get(motivation, 0.0))

    elimination_bonus = 0.08 if bool(match.get("is_elimination", False)) else 0.0
    overtime_bonus = 0.06 if bool(match.get("overtime_possible", False)) else 0.0

    base = 0.55
    score = _clip(base + motivation_bonus + elimination_bonus + overtime_bonus)

    flags: list[str] = []
    if motivation == "midtable" and not match.get("is_elimination", False):
        flags.append("lower_match_urgency")
    return score, flags


def _win_probability_context_score(team: dict[str, Any], opponent: dict[str, Any]) -> tuple[float, list[str]]:
    team_prob = _normalize_probability(team.get("team_win_probability"), default=0.5)
    opp_prob = _normalize_probability(opponent.get("team_win_probability"), default=0.5)
    win_prob_component = (team_prob - 0.5) * 0.8
    matchup_edge_component = (team_prob - opp_prob) * 0.2
    score = _clip(0.5 + win_prob_component + matchup_edge_component)

    flags: list[str] = []
    if team_prob < 0.33:
        flags.append("low_team_win_probability")
    if team_prob > 0.62:
        flags.append("strong_favorite_context")
    return score, flags


def _last_5_form_momentum_score(team: dict[str, Any]) -> tuple[float, list[str]]:
    results = team.get("last_5_results") or []
    if not isinstance(results, list) or len(results) != 5:
        return 0.5, ["missing_last_5_results"]

    normalized_results = [_normalize_last_5_result(item) for item in results]
    if any(item is None for item in normalized_results):
        return 0.5, ["unrecognized_last_5_results"]

    points_map = {"W": 1.0, "D": 0.5, "L": 0.0}
    recency_weights = [0.12, 0.16, 0.2, 0.24, 0.28]
    weighted_score = 0.0
    for result, weight in zip(normalized_results, recency_weights):
        weighted_score += points_map[result] * weight
    score = _clip(weighted_score)

    flags: list[str] = []
    wins = sum(1 for item in normalized_results if item == "W")
    if wins >= 4:
        flags.append("strong_last_5_form")
    if wins == 0:
        flags.append("poor_last_5_form")
    return score, flags


def _home_away_adjustment_score(team: dict[str, Any], cfg: dict[str, Any]) -> tuple[float, list[str]]:
    home_away_cfg = cfg.get("calibration", {}).get("home_away", {})
    home_bonus = float(home_away_cfg.get("home_bonus", 0.08))
    away_penalty = float(home_away_cfg.get("away_penalty", 0.06))
    venue_context = str(team.get("home_away", "away")).lower()

    base = 0.5
    if venue_context == "home":
        return _clip(base + home_bonus), ["home_context"]
    if venue_context == "away":
        return _clip(base - away_penalty), ["away_context"]
    return base, ["unknown_venue_context"]


def _weather_score(match: dict[str, Any], market_type: str, cfg: dict[str, Any]) -> tuple[float, list[str]]:
    weather = match.get("weather", {})
    rain_prob = float(weather.get("precipitation_probability", 0.0))
    wind = float(weather.get("wind_kph", 0.0))

    weather_cfg = cfg["calibration"]["weather"]
    rain_hit = rain_prob >= float(weather_cfg["rain_probability_threshold"])
    wind_hit = wind >= float(weather_cfg["wind_kph_threshold"])

    penalty = 0.0
    flags: list[str] = []
    if rain_hit or wind_hit:
        penalty = float(weather_cfg["pass_penalty"] if market_type == "passes" else weather_cfg["shots_penalty"])
        flags.append("adverse_weather")
        if market_type == "passes":
            flags.append("weather_penalty_on_pass_volume")

    return _clip(1.0 - penalty), flags


def _build_factor_payload(factors: dict[str, dict[str, Any]], contribution_floor: float) -> list[dict[str, Any]]:
    ordered = sorted(
        factors.items(),
        key=lambda item: item[1]["weighted_contribution"],
        reverse=True,
    )
    return [
        {
            "factor": name,
            "score": round(meta["score"], 4),
            "weight": round(meta["weight"], 4),
            "weighted_contribution": round(meta["weighted_contribution"], 4),
        }
        for name, meta in ordered
        if meta["weighted_contribution"] >= contribution_floor
    ]


def _resolve_direction_and_recommendation(
    *,
    baseline: float,
    line: Any,
    confidence: str,
    min_confidence_for_bet: str,
    guardrail_warnings: list[str],
    cfg: dict[str, Any],
) -> tuple[str, str, list[str]]:
    edge_cfg = cfg.get("global", {}).get("directional_edge", {})
    min_edge = float(edge_cfg.get("min_absolute_edge", 0.2))
    guardrail_cfg = cfg.get("global", {}).get("guardrail_thresholds", {})
    severe_warning_threshold = int(guardrail_cfg.get("severe_blocking_warning_count", 2))

    confidence_rank = {"low": 0, "medium": 1, "high": 2}
    confidence_ok = confidence_rank.get(confidence, 0) >= confidence_rank.get(min_confidence_for_bet, 1)

    try:
        market_line = float(line)
    except (TypeError, ValueError):
        return "over", "no-bet", ["market_line_missing"]

    edge = baseline - market_line
    direction = "over" if edge > 0 else "under"
    if abs(edge) < min_edge:
        return direction, "no-bet", ["insufficient_projection_edge"]

    guardrail_warning_count = len(guardrail_warnings)
    if guardrail_warning_count >= severe_warning_threshold:
        return direction, "no-bet", ["severe_guardrail_conditions"]

    if not confidence_ok:
        return direction, "no-bet", ["below_confidence_threshold"]
    return direction, "bet", []


def _score_market_candidate(
    player: dict[str, Any],
    market_type: str,
    match_inputs: dict[str, Any],
    teams_by_id: dict[str, dict[str, Any]],
    guardrails: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    team = teams_by_id.get(player.get("team_id"), {})
    opponent = next((t for tid, t in teams_by_id.items() if tid != player.get("team_id")), {})
    match = match_inputs.get("match", {})
    market_block = match_inputs.get("market", {})
    minutes_score, minutes_flags = _minutes_sub_score(player, cfg)
    role_score, role_flags = _role_score(player, market_type, cfg)
    poss_score, poss_flags = _possession_opponent_style_score(team, opponent, cfg)
    win_prob_score, win_prob_flags = _win_probability_context_score(team, opponent)
    form_score, form_flags = _last_5_form_momentum_score(team)
    home_away_score, home_away_flags = _home_away_adjustment_score(team, cfg)
    state_score, state_flags = _match_state_score(match, team, cfg)
    weather_score, weather_flags = _weather_score(match, market_type, cfg)
    market_score, market_flags = _market_agreement(player, market_block)

    weights = cfg[market_type]["factor_weights"]
    factors = {
        "minutes_sub_risk": {"score": minutes_score, "weight": float(weights["minutes_sub_risk"])},
        "role_opportunity": {"score": role_score, "weight": float(weights["role_opportunity"])},
        "team_possession_opponent_style": {
            "score": poss_score,
            "weight": float(weights["team_possession_opponent_style"]),
        },
        "win_probability_context": {"score": win_prob_score, "weight": float(weights["win_probability_context"])},
        "last_5_form_momentum": {"score": form_score, "weight": float(weights["last_5_form_momentum"])},
        "home_away_adjustment": {"score": home_away_score, "weight": float(weights["home_away_adjustment"])},
        "match_state_context": {"score": state_score, "weight": float(weights["match_state_context"])},
        "weather_penalty": {"score": weather_score, "weight": float(weights["weather_penalty"])},
        "market_agreement": {"score": market_score, "weight": float(weights["market_agreement"])},
    }

    for meta in factors.values():
        meta["weighted_contribution"] = meta["score"] * meta["weight"]

    overall_score = sum(meta["weighted_contribution"] for meta in factors.values())
    baseline_key = "expected_passes_baseline" if market_type == "passes" else "expected_shots_baseline"
    baseline = float(player.get(baseline_key, 0.0))

    confidence = "low"
    if overall_score >= 0.76:
        confidence = "high"
    elif overall_score >= 0.6:
        confidence = "medium"

    all_flags = sorted(
        set(
            minutes_flags
            + role_flags
            + poss_flags
            + win_prob_flags
            + form_flags
            + home_away_flags
            + state_flags
            + weather_flags
            + market_flags
        )
    )
    blocking_warnings = guardrails.get("blocking_warnings", [])
    if blocking_warnings:
        overall_score = _clip(overall_score - 0.12)
        confidence = _degrade_confidence(confidence)
        all_flags = sorted(set(all_flags + ["blocking_warning_active"] + list(blocking_warnings)))

    min_confidence_for_bet = str(cfg.get("global", {}).get("min_confidence_for_bet", "medium")).lower()
    line = player.get("market_lines", {}).get(market_type)
    try:
        directional_edge = round(baseline - float(line), 4)
    except (TypeError, ValueError):
        directional_edge = 0.0
    direction, recommendation, direction_flags = _resolve_direction_and_recommendation(
        baseline=baseline,
        line=line,
        confidence=confidence,
        min_confidence_for_bet=min_confidence_for_bet,
        guardrail_warnings=list(blocking_warnings),
        cfg=cfg,
    )
    all_flags = sorted(set(all_flags + direction_flags))
    explainability = {
        "top_contributing_factors": _build_factor_payload(
            factors,
            float(cfg["global"].get("contribution_floor", 0.0)),
        )[:3],
        "context_signals": {
            "win_probability_context": round(win_prob_score, 4),
            "last_5_form_momentum": round(form_score, 4),
            "home_away_adjustment": round(home_away_score, 4),
        },
        "risk_flags": all_flags,
    }

    return {
        "match_id": match_inputs.get("match_id") or match_inputs.get("match", {}).get("match_id"),
        "competition": match_inputs.get("competition") or match_inputs.get("match", {}).get("competition_type"),
        "player_id": player.get("player_id"),
        "player": player.get("player_name"),
        "team_id": player.get("team_id"),
        "market": market_type,
        "line": line,
        "direction": direction,
        "directional_edge": directional_edge,
        "score": round(overall_score, 4),
        "confidence": confidence,
        "recommendation": recommendation,
        "baseline_projection": round(baseline, 4),
        "market_agreement_score": round(market_score, 4),
        "model_version": str(cfg.get("global", {}).get("model_version", "unknown")),
        "explainability": explainability,
    }


def _build_reasoning_trace(
    *,
    selected: list[dict[str, Any]],
    match_inputs: dict[str, Any],
    guardrails: dict[str, Any],
) -> dict[str, Any]:
    teams = match_inputs.get("teams", [])
    home = next((team for team in teams if team.get("home_away") == "home"), teams[0] if teams else {})
    away = next((team for team in teams if team.get("home_away") == "away"), teams[1] if len(teams) > 1 else {})

    picks: list[dict[str, Any]] = []
    for rank, candidate in enumerate(selected, start=1):
        factors = candidate.get("explainability", {}).get("top_contributing_factors", [])
        tactical_fit = factors[0]["factor"] if factors else "unknown"
        risk_tags = [str(flag) for flag in candidate.get("explainability", {}).get("risk_flags", [])]
        no_bet_reasons = [
            tag
            for tag in risk_tags
            if tag
            in {
                "insufficient_projection_edge",
                "ambiguous_direction",
                "below_confidence_threshold",
                "market_line_missing",
                "severe_guardrail_conditions",
            }
        ]
        minutes_signal = next((flag for flag in risk_tags if "minutes" in flag or "substitution" in flag), "stable_minutes")
        why_line = "; ".join(f"{item.get('factor')}={item.get('score')}" for item in factors[:2]) or "model score"

        picks.append(
            {
                "rank": rank,
                "player_id": candidate.get("player_id"),
                "market": candidate.get("market"),
                "direction": candidate.get("direction"),
                "recommendation": candidate.get("recommendation"),
                "confidence": candidate.get("confidence"),
                "risk_tags": risk_tags,
                "no_bet_reasons": no_bet_reasons,
                "rationale": {
                    "minutes_signal": minutes_signal,
                    "tactical_fit": tactical_fit,
                    "notes": ", ".join(risk_tags) or "none",
                    "primary_risks_summary": ", ".join(risk_tags) or "none",
                    "why_this_pick": why_line,
                },
            }
        )

    return {
        "schema_version": "v1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "llm_provider": "none",
        "llm_model": "none",
        "llm_latency_ms": 0,
        "llm_status": "not_requested",
        "llm_fallback_used": False,
        "match_context_summary": {
            "match_id": str(match_inputs.get("match_id") or match_inputs.get("match", {}).get("match_id") or "unknown"),
            "fixture": f"{home.get('team_name', 'unknown')} vs {away.get('team_name', 'unknown')}",
            "competition": str(match_inputs.get("competition") or match_inputs.get("match", {}).get("competition_type") or "unknown"),
            "kickoff_utc": str(match_inputs.get("match", {}).get("kickoff_utc", "unknown")),
        },
        "guardrail_results": {
            "required_timestamps": guardrails.get("required_timestamps", {}),
            "blocking_warnings": guardrails.get("blocking_warnings", []),
            "missing_freshness_timestamps": guardrails.get("missing_freshness_timestamps", []),
            "guardrails_passed": not bool(guardrails.get("blocking_warnings") or guardrails.get("missing_freshness_timestamps")),
        },
        "picks": picks,
    }


def score_props(
    match_inputs: dict[str, Any],
    config_path: str | None = None,
    include_trace: bool = False,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Return top-five scored props for a requested match."""
    cfg = _load_config(config_path)
    guardrails = _evaluate_guardrails(match_inputs, cfg)
    if guardrails["missing_freshness_timestamps"]:
        raise ValueError(
            "Missing required freshness timestamps: "
            + ", ".join(guardrails["missing_freshness_timestamps"])
        )

    players = match_inputs.get("players", [])
    teams_by_id = _team_index(match_inputs)
    candidates: list[dict[str, Any]] = []

    for player in players:
        candidates.append(_score_market_candidate(player, "passes", match_inputs, teams_by_id, guardrails, cfg))
        candidates.append(_score_market_candidate(player, "shots", match_inputs, teams_by_id, guardrails, cfg))

    candidates.sort(key=lambda item: item["score"], reverse=True)
    top_k = int(cfg["global"].get("top_k", 5))
    if len(candidates) < top_k:
        raise ValueError(f"Need at least {top_k} scored candidates, found {len(candidates)}")
    selected = candidates[:top_k]
    for candidate in selected:
        candidate["guardrails"] = {
            "blocking_warnings": guardrails["blocking_warnings"],
            "required_timestamps": guardrails["required_timestamps"],
        }

    if not include_trace:
        return selected

    trace = _build_reasoning_trace(selected=selected, match_inputs=match_inputs, guardrails=guardrails)
    return {"scores": selected, "trace": trace}


def main() -> None:
    parser = argparse.ArgumentParser(description="Score soccer player props.")
    parser.add_argument(
        "--input-json",
        default="{}",
        help="Serialized match input payload",
    )
    parser.add_argument(
        "--config-path",
        default=None,
        help="Optional scoring config path (defaults to repo config).",
    )
    parser.add_argument(
        "--emit-trace",
        action="store_true",
        help="Emit normalized reasoning trace with scored picks.",
    )
    args = parser.parse_args()

    match_inputs = json.loads(args.input_json)
    results = score_props(match_inputs, config_path=args.config_path, include_trace=args.emit_trace)
    print(json.dumps(results))


if __name__ == "__main__":
    main()
