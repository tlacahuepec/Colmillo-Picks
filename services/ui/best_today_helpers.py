"""Pure helper functions for the Best Today slate page.

Kept separate from the Streamlit runtime so they can be unit-tested directly.
"""

from __future__ import annotations

from typing import Any

_DEFAULT_SPORTS = ["soccer", "basketball", "baseball"]

_CONFIDENCE_COLORS: dict[str, str] = {
    "high": "green",
    "medium": "orange",
    "low": "red",
}

_SLATE_CACHE_KEY = "last_slate_detail"


def build_slate_payload(
    *,
    date: str,
    sports: list[str],
    max_matches_per_sport: int,
    top_n: int,
) -> dict[str, Any]:
    return {
        "date": date,
        "sports": sports if sports else _DEFAULT_SPORTS,
        "max_matches_per_sport": max_matches_per_sport,
        "top_n": top_n,
    }


def format_slate_candidate_row(candidate: dict[str, Any]) -> str:
    rank = candidate.get("rank", "?")
    sport = candidate.get("sport", "?")
    player = candidate.get("player", "Unknown")
    market = candidate.get("market", "?")
    line = candidate.get("line")
    direction = candidate.get("direction", "?")
    confidence = candidate.get("confidence", "?")
    score = candidate.get("normalized_score", 0)
    risk_flags = candidate.get("risk_flags", [])
    source_match = candidate.get("source_match", {})
    home = source_match.get("home_team", "")
    away = source_match.get("away_team", "")

    line_str = f" {line}" if line is not None else ""
    match_str = f"{home} v {away}" if home and away else ""
    risk_str = f" | risks: {', '.join(risk_flags)}" if risk_flags else ""

    return (
        f"#{rank} [{sport}] {player} — {market}{line_str} {direction} "
        f"(score: {score:.0f}, confidence: {confidence})"
        f"{f' | {match_str}' if match_str else ''}{risk_str}"
    )


def format_match_run_summary(run: dict[str, Any]) -> str:
    sport = run.get("sport", "?")
    home = run.get("home_team", "?")
    away = run.get("away_team", "?")
    status = run.get("status", "?")
    pick_count = run.get("pick_count", 0)
    latency = run.get("latency_ms")
    error_msg = run.get("error_message", "")

    latency_str = f" ({latency}ms)" if latency else ""

    if status == "success":
        return f"[{sport}] {home} v {away} — success, {pick_count} picks{latency_str}"
    return f"[{sport}] {home} v {away} — failed: {error_msg}{latency_str}"


def render_no_candidates_message() -> str:
    return "No actionable picks found. All match pipelines either failed or produced no viable candidates."


def render_partial_failure_summary(match_runs: list[dict[str, Any]]) -> str:
    failed = [r for r in match_runs if r.get("status") == "failed"]
    if not failed:
        return ""
    lines = []
    for run in failed:
        home = run.get("home_team", "?")
        away = run.get("away_team", "?")
        sport = run.get("sport", "?")
        error = run.get("error_message", "unknown error")
        lines.append(f"- [{sport}] {home} v {away}: failed — {error}")
    return "\n".join(lines)


def store_slate_result(session_state: dict[str, Any], detail: dict[str, Any]) -> None:
    session_state[_SLATE_CACHE_KEY] = detail


def clear_slate_cache(session_state: dict[str, Any]) -> None:
    session_state.pop(_SLATE_CACHE_KEY, None)


def should_render_cached_slate(session_state: dict[str, Any]) -> bool:
    return _SLATE_CACHE_KEY in session_state


def confidence_color(confidence: str) -> str:
    return _CONFIDENCE_COLORS.get(confidence.lower(), "gray")


def format_risk_flags_markdown(risk_flags: list[str]) -> str:
    if not risk_flags:
        return ""
    return " ".join(f"`{flag}`" for flag in risk_flags)


def build_availability_batch_payload(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for c in candidates:
        player = c.get("player", "")
        market = c.get("market", "")
        if not player or not market:
            continue
        payload.append({
            "player": player,
            "market": market,
            "line": c.get("line") or 0.0,
        })
    return payload


def match_badges_to_candidates(
    badges: list[dict[str, Any]], candidates: list[dict[str, Any]]
) -> dict[int, dict[str, Any]]:
    if not badges:
        return {}
    badge_map: dict[tuple[str, str], dict[str, Any]] = {}
    for badge in badges:
        key = (badge.get("player", ""), badge.get("market", ""))
        badge_map[key] = badge

    result: dict[int, dict[str, Any]] = {}
    for idx, candidate in enumerate(candidates):
        key = (candidate.get("player", ""), candidate.get("market", ""))
        if key in badge_map:
            result[idx] = badge_map[key]
    return result


def format_source_pick_detail(source_pick: dict[str, Any]) -> str:
    if not source_pick:
        return ""
    lines: list[str] = []
    score = source_pick.get("score")
    if score is not None:
        lines.append(f"**Score:** {score}")
    rationale = source_pick.get("llm_rationale")
    if rationale:
        lines.append(f"**Reasoning:** {rationale}")
    factors = source_pick.get("factors")
    if factors and isinstance(factors, dict):
        factor_parts = [f"{k}: {v}" for k, v in factors.items()]
        lines.append(f"**Factors:** {', '.join(factor_parts)}")
    return "\n\n".join(lines)
