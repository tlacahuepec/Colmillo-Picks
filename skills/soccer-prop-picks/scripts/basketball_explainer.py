"""Basketball-specific explanation builder.

Generates human-readable explanations for basketball picks using
evidence from the scored pick data. Does not recalculate scores.
"""

from __future__ import annotations

from typing import Any


def explain_basketball_pick(pick: dict[str, Any]) -> str:
    player = pick.get("player", "Unknown")
    market = pick.get("market", "unknown")
    direction = pick.get("direction", "over").upper()
    line = pick.get("line", 0)
    confidence = pick.get("confidence", "medium")
    explainability = pick.get("explainability", {})
    evidence = explainability.get("evidence", {})
    risk_flags = explainability.get("risk_flags", [])

    parts: list[str] = []
    parts.append(f"{player} — {direction} {line} {market} (confidence: {confidence})")

    evidence_lines = _build_evidence_lines(evidence, market)
    if evidence_lines:
        parts.append("Evidence: " + "; ".join(evidence_lines))

    if risk_flags:
        risk_text = _format_risk_flags(risk_flags)
        parts.append(f"Risks/Limitations: {risk_text}")

    return "\n".join(parts)


def _build_evidence_lines(evidence: dict[str, Any], market: str) -> list[str]:
    lines: list[str] = []

    minutes = evidence.get("minutes_proj")
    if minutes is not None:
        lines.append(f"projected minutes {minutes}")

    usage = evidence.get("usage_rate")
    if usage is not None:
        lines.append(f"usage rate {usage:.0%}")

    pace = evidence.get("pace_factor")
    if pace is not None:
        if pace > 1.0:
            lines.append(f"pace advantage ({pace:.2f}x)")
        elif pace < 1.0:
            lines.append(f"slower pace ({pace:.2f}x)")

    avg_key = f"{market}_avg"
    last5_key = f"{market}_last5"
    avg = evidence.get(avg_key) or evidence.get("points_avg")
    last5 = evidence.get(last5_key) or evidence.get("points_last5")
    if avg is not None and last5 is not None:
        if last5 > avg:
            lines.append(f"recent form trending up ({avg} → {last5})")
        elif last5 < avg:
            lines.append(f"recent form trending down ({avg} → {last5})")

    opp_rank = evidence.get("opp_rebound_rank")
    if opp_rank is not None:
        if opp_rank > 20:
            lines.append(f"favorable matchup (opponent rank {opp_rank})")
        elif opp_rank < 10:
            lines.append(f"tough matchup (opponent rank {opp_rank})")
        else:
            lines.append(f"neutral matchup (opponent rank {opp_rank})")

    return lines


def _format_risk_flags(flags: list[str]) -> str:
    descriptions = {
        "missing_data": "limited data available",
        "placeholder_scoring": "using placeholder scoring model",
        "injury_concern": "injury risk present",
        "blowout_risk": "potential blowout scenario",
    }
    parts = [descriptions.get(f, f) for f in flags]
    return "; ".join(parts)
