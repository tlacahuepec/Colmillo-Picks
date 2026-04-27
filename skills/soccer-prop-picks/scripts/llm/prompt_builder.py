from __future__ import annotations

from typing import Any


def build_system_prompt() -> str:
    """Return static system instructions for schema-constrained soccer prop reasoning."""
    return (
        "You are an expert soccer prop analyst. "
        "Use only the provided match context and scored candidates. "
        "Return schema-compliant JSON only. "
        "Do not include markdown, prose outside JSON, or code fences."
    )


def build_user_prompt(match_inputs: dict[str, Any], scored_props: list[dict[str, Any]], top_n: int) -> str:
    """Build a deterministic user prompt payload from curated, relevant fields only."""
    teams = match_inputs.get("teams", [])
    home_name = _team_name(teams, "home")
    away_name = _team_name(teams, "away")

    lines: list[str] = [
        "Match context:",
        f"- match_id: {match_inputs.get('match_id', 'unknown')}",
        f"- competition: {match_inputs.get('competition', 'unknown')}",
        f"- fixture: {home_name} vs {away_name}",
        f"- kickoff_utc: {match_inputs.get('match', {}).get('kickoff_utc', 'unknown')}",
        "",
        f"Top {max(top_n, 0)} candidate props:",
    ]

    for rank, prop in enumerate(scored_props[: max(top_n, 0)], start=1):
        risk_flags = _extract_risk_flags(prop)
        lines.append(
            " | ".join(
                [
                    f"{rank}. {prop.get('player_id', 'unknown')}",
                    str(prop.get("player_name", "unknown")),
                    str(prop.get("team_id", "unknown")),
                    f"{prop.get('market', 'unknown')} {prop.get('line', 'n/a')}",
                    str(prop.get("direction", "unknown")),
                    str(prop.get("recommendation", "unknown")),
                    f"confidence={prop.get('confidence', 'unknown')}",
                    f"score={_format_score(prop.get('score'))}",
                ]
            )
        )
        lines.append(f"   risk_flags: {'; '.join(risk_flags) if risk_flags else 'none'}")

    lines.extend(["", "Return only schema-compliant JSON."])
    return "\n".join(lines)


def _team_name(teams: list[dict[str, Any]], side: str) -> str:
    for team in teams:
        if str(team.get("home_away", "")).lower() == side:
            return str(team.get("team_name") or team.get("team_id") or "unknown")
    return "unknown"


def _extract_risk_flags(prop: dict[str, Any]) -> list[str]:
    guardrails = prop.get("guardrails", {})
    blocking = guardrails.get("blocking_warnings") or []
    missing = guardrails.get("missing_freshness_timestamps") or []
    flags = [str(item) for item in [*blocking, *missing] if str(item).strip()]
    return sorted(dict.fromkeys(flags))


def _format_score(raw_score: Any) -> str:
    try:
        return f"{float(raw_score):.2f}"
    except (TypeError, ValueError):
        return "n/a"
