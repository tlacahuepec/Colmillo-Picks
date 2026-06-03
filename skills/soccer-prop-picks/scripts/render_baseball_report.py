"""MLB report renderer with responsible gaming guardrails.

Generates markdown reports for MLB pick recommendations. Every report
includes data quality indicators, confidence levels, source audit,
and responsible gaming messaging.
"""

from __future__ import annotations

from typing import Any

RESPONSIBLE_GAMING_DISCLAIMER = (
    "---\n"
    "**Responsible Gaming:** Sports betting involves risk. Never wager more than you can afford to lose. "
    "If you or someone you know has a gambling problem, call the National Council on Problem Gambling "
    "helpline: **1-800-522-4700** or visit [ncpgambling.org](https://www.ncpgambling.org)."
)


def render_baseball_report(
    *,
    match_context: dict[str, Any],
    picks: list[dict[str, Any]],
    no_bet_picks: list[dict[str, Any]] | None = None,
    provider_statuses: list[dict[str, Any]] | None = None,
) -> str:
    no_bet_picks = list(no_bet_picks or [])
    provider_statuses = provider_statuses or []

    valid_picks: list[dict[str, Any]] = []
    for pick in picks:
        if not pick.get("line"):
            no_bet_picks.append({
                "player": pick.get("player", "Unknown"),
                "market": pick.get("market", "unknown"),
                "reason": "zero_line_data_gap",
            })
        else:
            valid_picks.append(pick)
    picks = valid_picks

    sections: list[str] = []
    sections.append(_render_matchup_summary(match_context))
    sections.append(_render_data_quality(match_context))

    if picks:
        sections.append(_render_picks_table(picks))
    else:
        sections.append(_render_no_picks_message())

    if no_bet_picks:
        sections.append(_render_no_bet_section(no_bet_picks))

    if provider_statuses:
        sections.append(_render_source_audit(provider_statuses))

    sections.append(RESPONSIBLE_GAMING_DISCLAIMER)
    return "\n\n".join(sections)


def _render_matchup_summary(ctx: dict[str, Any]) -> str:
    home = ctx.get("home_team", "TBD")
    away = ctx.get("away_team", "TBD")
    venue = ctx.get("venue", "Unknown")
    game_time = ctx.get("game_time_utc", "TBD")
    home_pitcher = ctx.get("home_probable_pitcher", "TBD")
    away_pitcher = ctx.get("away_probable_pitcher", "TBD")
    weather = ctx.get("weather", {})

    lines = [
        f"## {away} @ {home}",
        f"**Venue:** {venue} | **First Pitch:** {game_time}",
        f"**Probable Pitchers:** {away_pitcher} vs {home_pitcher}",
    ]

    if weather:
        temp = weather.get("temp_f")
        wind_mph = weather.get("wind_mph")
        wind_dir = weather.get("wind_direction", "")
        dome = weather.get("dome", False)
        if dome:
            lines.append("**Weather:** Dome (controlled environment)")
        elif temp is not None:
            wind_str = f", wind {wind_mph} mph {wind_dir}" if wind_mph else ""
            lines.append(f"**Weather:** {temp}\u00b0F{wind_str}")

    return "\n".join(lines)


def _render_data_quality(ctx: dict[str, Any]) -> str:
    dq = ctx.get("data_quality", {})
    if not dq:
        return "### Data Quality\n| Item | Status |\n|------|--------|\n| Lineup | unverified |\n| Pitcher | unverified |\n| Weather | unverified |\n| Odds | unverified |"

    lines = ["### Data Quality", "| Item | Status |", "|------|--------|"]
    for key, status in dq.items():
        label = key.replace("_status", "").replace("_", " ").title()
        lines.append(f"| {label} | {status} |")
    return "\n".join(lines)


def _render_picks_table(picks: list[dict[str, Any]]) -> str:
    lines = [
        "### Recommended Picks",
        "| Player | Market | Direction | Line | Confidence | Top Risk |",
        "|--------|--------|-----------|------|------------|----------|",
    ]

    for pick in picks:
        player = pick.get("player", "Unknown")
        market = pick.get("market", "unknown")
        direction = pick.get("direction", "over").upper()
        line = pick.get("line", 0)
        confidence = pick.get("confidence", "medium").capitalize()
        risk_flags = pick.get("risk_flags", [])
        top_risk = risk_flags[0] if risk_flags else "none"
        lines.append(f"| {player} | {market} | {direction} | {line} | {confidence} | {top_risk} |")

    lines.append("")
    lines.append("#### Pick Details")
    for pick in picks:
        player = pick.get("player", "Unknown")
        market = pick.get("market", "unknown")
        explanation = pick.get("explanation", "")
        factors = pick.get("top_factors", [])
        factor_str = ", ".join(f"{f['factor']} ({f['score']:.2f})" for f in factors[:3]) if factors else "N/A"
        lines.append(f"\n**{player} — {market}**")
        lines.append(f"- Top factors: {factor_str}")
        if explanation:
            lines.append(f"- {explanation}")

    return "\n".join(lines)


def _render_no_picks_message() -> str:
    return (
        "### Picks\n"
        "**No actionable picks available for this matchup.** "
        "All markets were blocked due to data quality or guardrail constraints. "
        "See the NO-BET section below for details."
    )


def _render_no_bet_section(no_bet_picks: list[dict[str, Any]]) -> str:
    lines = [
        "### NO-BET Markets",
        "The following markets were blocked from recommendation:",
        "",
        "| Player | Market | Reason |",
        "|--------|--------|--------|",
    ]
    for entry in no_bet_picks:
        player = entry.get("player", "Unknown")
        market = entry.get("market", "unknown")
        reason = entry.get("reason", "unspecified")
        lines.append(f"| {player} | {market} | {reason} |")

    return "\n".join(lines)


def _render_source_audit(statuses: list[dict[str, Any]]) -> str:
    lines = [
        "### Source Audit",
        "| Provider | Data Type | Timestamp | Freshness |",
        "|----------|-----------|-----------|-----------|",
    ]
    for entry in statuses:
        provider = entry.get("provider", "unknown")
        data_type = entry.get("data_type", "unknown")
        timestamp = entry.get("timestamp", "N/A")
        status = entry.get("status", "unknown")
        lines.append(f"| {provider} | {data_type} | {timestamp} | {status} |")

    return "\n".join(lines)
