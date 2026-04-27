#!/usr/bin/env python3
"""Render top soccer prop picks into a standardized report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "templates" / "pick_report.md"


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "unknown"
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "unknown"


def _join_names(items: list[dict[str, Any]]) -> str:
    if not items:
        return "none"
    return ", ".join(
        f"{item.get('player_name', 'unknown')} ({item.get('status', 'unknown')})"
        for item in items
    )


def _standings_line(team: dict[str, Any]) -> dict[str, Any]:
    standings = team.get("standings_context", {})
    return {
        "table_position": standings.get("table_position", "unknown"),
        "points": standings.get("points", "unknown"),
        "games_played": standings.get("games_played", "unknown"),
        "motivation_tag": standings.get("motivation_tag", "unknown"),
    }


def _build_match_summary(match_inputs: dict[str, Any]) -> dict[str, str]:
    match = match_inputs.get("match", {})
    teams = match_inputs.get("teams", [])

    home = next((team for team in teams if team.get("home_away") == "home"), teams[0] if teams else {})
    away = next((team for team in teams if team.get("home_away") == "away"), teams[1] if len(teams) > 1 else {})

    home_lineup = home.get("projected_lineup", {})
    away_lineup = away.get("projected_lineup", {})

    home_standings = _standings_line(home)
    away_standings = _standings_line(away)

    weather = match.get("weather", {})
    venue = match.get("venue", {})

    return {
        "home_team": str(home.get("team_name", "unknown")),
        "away_team": str(away.get("team_name", "unknown")),
        "competition_type": str(match.get("competition_type", "unknown")),
        "kickoff_utc": str(match.get("kickoff_utc", "unknown")),
        "venue_name": str(venue.get("name", "unknown")),
        "venue_city": str(venue.get("city", "unknown")),
        "venue_country": str(venue.get("country", "unknown")),
        "weather_summary": str(weather.get("summary", "unknown")),
        "temperature_c": str(weather.get("temperature_c", "unknown")),
        "wind_kph": str(weather.get("wind_kph", "unknown")),
        "precipitation_probability": _fmt_pct(weather.get("precipitation_probability")),
        "home_lineup_status": str(home_lineup.get("status", "unknown")),
        "home_formation": str(home_lineup.get("formation", "unknown")),
        "home_starters": ", ".join(home_lineup.get("starters", [])) or "unknown",
        "away_lineup_status": str(away_lineup.get("status", "unknown")),
        "away_formation": str(away_lineup.get("formation", "unknown")),
        "away_starters": ", ".join(away_lineup.get("starters", [])) or "unknown",
        "home_injuries_suspensions": _join_names(home.get("injuries", [])) + "; " + _join_names(home.get("suspensions", [])),
        "away_injuries_suspensions": _join_names(away.get("injuries", [])) + "; " + _join_names(away.get("suspensions", [])),
        "home_table_position": str(home_standings["table_position"]),
        "home_points": str(home_standings["points"]),
        "home_games_played": str(home_standings["games_played"]),
        "home_motivation_tag": str(home_standings["motivation_tag"]),
        "away_table_position": str(away_standings["table_position"]),
        "away_points": str(away_standings["points"]),
        "away_games_played": str(away_standings["games_played"]),
        "away_motivation_tag": str(away_standings["motivation_tag"]),
    }


def _trace_index(trace: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    picks = (trace or {}).get("picks", [])
    return {f"{item.get('player_id')}:{item.get('market')}": item for item in picks}


def _candidate_evidence_rows(scored_props: list[dict[str, Any]], trace: dict[str, Any] | None = None) -> str:
    rows = []
    trace_by_pick = _trace_index(trace)
    for candidate in scored_props:
        key = f"{candidate.get('player_id')}:{candidate.get('market')}"
        trace_pick = trace_by_pick.get(key, {})
        rationale = trace_pick.get("rationale", {})
        factors = candidate.get("explainability", {}).get("top_contributing_factors", [])
        tactical_fit = rationale.get("tactical_fit") or (factors[0]["factor"] if factors else "unknown")
        trend_value = candidate.get("baseline_projection", "unknown")
        minutes_signal = rationale.get("minutes_signal") or next(
            (
                flag
                for flag in candidate.get("explainability", {}).get("risk_flags", [])
                if "minutes" in flag or "substitution" in flag
            ),
            "stable_minutes",
        )
        notes = rationale.get("notes") or ", ".join(candidate.get("explainability", {}).get("risk_flags", [])) or "none"

        rows.append(
            "| {player} | {team} | {market} | {line} | baseline={trend} | {minutes} | {fit} | {notes} |".format(
                player=candidate.get("player", "unknown"),
                team=candidate.get("team_id", "unknown"),
                market=candidate.get("market", "unknown"),
                line=candidate.get("line", "unknown"),
                trend=trend_value,
                minutes=minutes_signal,
                fit=tactical_fit,
                notes=notes,
            )
        )

    return "\n".join(rows) if rows else "| n/a | n/a | n/a | n/a | n/a | n/a | n/a | no candidates |"


def _top_pick_rows(scored_props: list[dict[str, Any]], top_n: int, trace: dict[str, Any] | None = None) -> str:
    rows = []
    trace_by_pick = _trace_index(trace)
    for rank, candidate in enumerate(scored_props[:top_n], start=1):
        key = f"{candidate.get('player_id')}:{candidate.get('market')}"
        trace_pick = trace_by_pick.get(key, {})
        rationale = trace_pick.get("rationale", {})
        risks = rationale.get("primary_risks_summary") or ", ".join(candidate.get("explainability", {}).get("risk_flags", [])) or "none"
        factors = candidate.get("explainability", {}).get("top_contributing_factors", [])
        why = rationale.get("why_this_pick") or "; ".join(f"{f.get('factor')}={f.get('score')}" for f in factors[:2]) or "model score"
        outcome = str(candidate.get("recommendation", "bet")).upper()
        direction = str(candidate.get("direction", "over")).title() if outcome != "NO-BET" else "No Bet"
        rows.append(
            "| {rank} | {player} | {team} | {market} | {direction} | {outcome} | {confidence} | {risks} | {why} |".format(
                rank=rank,
                player=candidate.get("player", "unknown"),
                team=candidate.get("team_id", "unknown"),
                market=candidate.get("market", "unknown"),
                direction=direction,
                outcome=outcome,
                confidence=str(candidate.get("confidence", "unknown")).title(),
                risks=risks,
                why=why,
            )
        )

    return "\n".join(rows) if rows else "| 1 | n/a | n/a | n/a | n/a | NO-BET | n/a | n/a | no picks |"


def _guardrail_warning_lines(scored_props: list[dict[str, Any]]) -> str:
    warnings: list[str] = []
    for candidate in scored_props:
        guardrails = candidate.get("guardrails", {})
        warnings.extend([str(item) for item in guardrails.get("blocking_warnings", [])])
    deduped = sorted(set(warnings))
    if not deduped:
        return "- none"
    return "\n".join(f"- {item}" for item in deduped)


def _audit_log_lines(scored_props: list[dict[str, Any]]) -> str:
    if not scored_props:
        return "| unknown | unknown | unknown | unknown |\n"
    guardrails = scored_props[0].get("guardrails", {})
    required = guardrails.get("required_timestamps", {})
    model_version = str(scored_props[0].get("model_version", "unknown"))
    return (
        "| {model} | {home} | {away} | {odds} | {weather} |\n".format(
            model=model_version,
            home=required.get("home_lineup_timestamp_utc", "unknown"),
            away=required.get("away_lineup_timestamp_utc", "unknown"),
            odds=required.get("odds_timestamp_utc", "unknown"),
            weather=required.get("weather_timestamp_utc", "unknown"),
        )
    )


def _resolve_final_availability(prizepicks: str, alternatives: list[str]) -> str:
    statuses = [prizepicks] + alternatives
    if any(status == "available" for status in statuses):
        return "available"
    if statuses and all(status == "unavailable" for status in statuses):
        return "unavailable"
    return "unknown"


def _availability_rows(scored_props: list[dict[str, Any]], top_n: int, availability_data: dict[str, Any]) -> str:
    now_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = []
    fallback_mode = bool(availability_data.get("fallback_mode", False))
    fallback_reason = availability_data.get("fallback_reason", "data fetch ok")

    for rank, candidate in enumerate(scored_props[:top_n], start=1):
        player_id = candidate.get("player_id")
        market = candidate.get("market")
        key = f"{player_id}:{market}"
        entry = availability_data.get("picks", {}).get(key, {})

        prizepicks_status = str(entry.get("prizepicks", "unknown"))
        alternatives = entry.get("alternatives", {})
        alt_summary_parts = [f"{name}:{status}" for name, status in alternatives.items()]
        alt_summary = ", ".join(alt_summary_parts) if alt_summary_parts else "none configured"

        retrieved_at = str(entry.get("retrieved_at_utc", now_utc))
        alt_statuses = [str(value) for value in alternatives.values()]
        final_status = str(entry.get("final_status") or _resolve_final_availability(prizepicks_status, alt_statuses))

        fallback_applied = "yes" if fallback_mode else "no"
        if fallback_mode:
            fallback_applied = f"yes ({fallback_reason})"

        rows.append(
            "| {rank} | {player} | {market} | {prizepicks} | {alternatives} | {final} | {retrieved} | {fallback} |".format(
                rank=rank,
                player=candidate.get("player", "unknown"),
                market=market,
                prizepicks=prizepicks_status,
                alternatives=alt_summary,
                final=final_status,
                retrieved=retrieved_at,
                fallback=fallback_applied,
            )
        )

    return "\n".join(rows) if rows else "| 1 | n/a | n/a | unknown | none configured | unknown | n/a | yes (no picks) |"


def render_report(
    scored_props: list[dict[str, Any]],
    match_inputs: dict[str, Any],
    availability_data: dict[str, Any] | None = None,
    top_n: int = 5,
    trace: dict[str, Any] | None = None,
) -> str:
    """Render a markdown report for top picks."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    availability_data = availability_data or {}

    match_summary = _build_match_summary(match_inputs)
    replacements = {
        **match_summary,
        "candidate_evidence_rows": _candidate_evidence_rows(scored_props, trace=trace),
        "top_5_pick_rows": _top_pick_rows(scored_props, top_n=top_n, trace=trace),
        "availability_rows": _availability_rows(scored_props, top_n=top_n, availability_data=availability_data),
        "guardrail_blocking_warnings": _guardrail_warning_lines(scored_props),
        "audit_log_rows": _audit_log_lines(scored_props),
        "critical_missing_fields": ", ".join(match_inputs.get("validation", {}).get("critical_missing_fields", [])) or "none",
        "should_reject_prediction": str(match_inputs.get("validation", {}).get("should_reject_prediction", False)).lower(),
    }

    report = template
    for key, value in replacements.items():
        report = report.replace(f"{{{{{key}}}}}", str(value))

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Render soccer prop pick report.")
    parser.add_argument("--top-n", type=int, default=5, help="Number of picks to render")
    parser.add_argument(
        "--input-json",
        default="[]",
        help="Serialized scored props payload",
    )
    parser.add_argument(
        "--match-input-json",
        default="{}",
        help="Serialized match input payload used for summary sections",
    )
    parser.add_argument(
        "--availability-json",
        default="{}",
        help="Serialized availability payload for PrizePicks/alternatives",
    )
    parser.add_argument(
        "--trace-json",
        default="{}",
        help="Optional serialized scoring trace payload",
    )
    args = parser.parse_args()

    scored_props = json.loads(args.input_json)
    match_inputs = json.loads(args.match_input_json)
    availability_data = json.loads(args.availability_json)
    trace = json.loads(args.trace_json)

    report = render_report(
        scored_props=scored_props,
        match_inputs=match_inputs,
        availability_data=availability_data,
        top_n=args.top_n,
        trace=trace,
    )
    print(report)


if __name__ == "__main__":
    main()
