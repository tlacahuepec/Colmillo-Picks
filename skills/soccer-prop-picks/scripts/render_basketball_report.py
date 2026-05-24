"""Render basketball prop pick scores into a markdown report."""

from __future__ import annotations

from typing import Any


def render_basketball_report(
    scores: list[dict[str, Any]],
    match_inputs: dict[str, Any],
    *,
    used_fallback: bool = False,
) -> str:
    sections: list[str] = []
    sections.append(_render_header(match_inputs))
    sections.append(_render_game_context(match_inputs.get("game", {})))
    sections.append(_render_picks_table(scores))
    sections.append(_render_pick_details(scores))
    sections.append(_render_data_quality(match_inputs, used_fallback))
    return "\n\n".join(s for s in sections if s)


def _render_header(match_inputs: dict[str, Any]) -> str:
    home = match_inputs.get("home_team", "Home")
    away = match_inputs.get("away_team", "Away")
    date = match_inputs.get("match_date", "")
    league = match_inputs.get("league", "nba").upper()
    return f"# {league} Pick Report: {home} vs {away}\n\n**Date:** {date}"


def _render_game_context(game: dict[str, Any]) -> str:
    if not game:
        return ""
    lines: list[str] = ["## Game Context"]
    venue = game.get("venue")
    if venue:
        lines.append(f"**Venue:** {venue}")

    pace = game.get("projected_game_pace") or game.get("home_pace")
    spread = game.get("spread")
    ou = game.get("over_under_total")
    home_rest = game.get("home_rest_days")
    away_rest = game.get("away_rest_days")

    stats: list[str] = []
    if pace is not None:
        stats.append(f"Pace: {pace}")
    if spread is not None:
        stats.append(f"Spread: {spread}")
    if ou is not None:
        stats.append(f"O/U: {ou}")
    if home_rest is not None:
        stats.append(f"Home rest: {home_rest}d")
    if away_rest is not None:
        stats.append(f"Away rest: {away_rest}d")

    if stats:
        lines.append(" | ".join(stats))

    return "\n\n".join(lines)


def _render_picks_table(scores: list[dict[str, Any]]) -> str:
    if not scores:
        return "## Top Picks\n\nNo actionable picks generated for this matchup."

    lines: list[str] = [
        "## Top Picks",
        "",
        "| # | Player | Market | Direction | Line | Score | Confidence |",
        "|---|--------|--------|-----------|------|-------|------------|",
    ]
    for rank, pick in enumerate(scores, start=1):
        lines.append(
            "| {rank} | {player} | {market} | {direction} | {line} | {score} | {confidence} |".format(
                rank=rank,
                player=pick.get("player", "Unknown"),
                market=pick.get("market", "unknown"),
                direction=pick.get("direction", "over").title(),
                line=pick.get("line", "-"),
                score=f"{pick.get('score', 0):.2f}",
                confidence=pick.get("confidence", "unknown").title(),
            )
        )
    return "\n".join(lines)


def _render_pick_details(scores: list[dict[str, Any]]) -> str:
    if not scores:
        return ""

    lines: list[str] = ["## Pick Details"]
    for pick in scores:
        player = pick.get("player", "Unknown")
        market = pick.get("market", "unknown")
        explainability = pick.get("explainability", {})
        factors = explainability.get("top_contributing_factors", [])
        risk_flags = explainability.get("risk_flags", [])

        lines.append(f"\n### {player} — {market}")
        if factors:
            lines.append("**Top factors:**")
            for f in factors[:3]:
                name = f.get("factor", "unknown")
                score = f.get("score", 0)
                weight = f.get("weight", 0)
                lines.append(f"- {name}: {score:.2f} (weight {weight:.2f})")
        if risk_flags:
            lines.append(f"**Risk flags:** {', '.join(risk_flags)}")

    return "\n".join(lines)


def _render_data_quality(match_inputs: dict[str, Any], used_fallback: bool) -> str:
    lines: list[str] = ["## Data Quality"]
    if used_fallback:
        lines.append(
            "⚠️ **Deterministic fallback used.** LLM providers were unavailable; "
            "picks are based on placeholder data and should not be used for real decisions."
        )
    else:
        game = match_inputs.get("game", {})
        if game:
            lines.append("Game context: available")
        else:
            lines.append("Game context: unavailable")
        player_count = len(match_inputs.get("players", []))
        lines.append(f"Players analyzed: {player_count}")
    return "\n\n".join(lines)
