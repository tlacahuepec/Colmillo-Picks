"""Subject-aware NFL reports with intact sportsbook evidence."""


def _text(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_nfl_report(scores, match_inputs):
    lines = [
        f"# NFL: {_text(match_inputs.get('home_team', ''))} v {_text(match_inputs.get('away_team', ''))}",
        "",
        "Full-game pregame picks. Scores are heuristic rankings, not win probabilities or expected returns.",
        "Sportsbook prices are snapshots; platform availability is checked separately. Grade NFL results manually.",
        "",
    ]
    if not scores:
        lines.append("No verified NFL picks qualified.")
    for rank, pick in enumerate(scores, 1):
        offer = pick["offer"]
        line = (
            f" {pick['line']:+g}"
            if pick["market"] == "spread"
            else f" {pick['line']:g}"
            if pick.get("line") is not None
            else ""
        )
        lines.extend(
            [
                f"## {rank}. {_text(pick['subject_name'])} — {_text(pick['market'])}{line} {_text(pick['selection'])}",
                f"Score: {pick['score']:.2f} · Confidence: {pick['confidence']}",
                f"Book: {_text(offer['sportsbook'])} · Decimal odds: {offer['odds_decimal']:g} · Observed: {_text(offer['observed_at'])}",
                f"[Sportsbook source]({offer['source_url']})",
                pick["explainability"]["rationale"],
            ]
        )
        for source in pick["explainability"].get("sources", []):
            lines.append(f"[Stat evidence]({source})")
        for factor in pick["explainability"]["top_contributing_factors"]:
            lines.append(
                f"- {factor['factor']}: {factor['score']:.2f} (weight {factor['weight']:.2f})"
            )
        flags = pick["explainability"]["risk_flags"]
        if flags:
            lines.append("Risks: " + ", ".join(flags))
        lines.append("")
    exclusions = match_inputs.get("exclusions", [])
    if exclusions:
        lines.extend(["", "## Missing data and excluded selections", ""])
        lines.extend(
            f"- {_text(e['subject'])}: {_text(e['reason'])}" for e in exclusions
        )
    return "\n".join(lines) + "\n"
