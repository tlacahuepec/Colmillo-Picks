#!/usr/bin/env python3
"""Audit grounding quality for basketball enrichment.

Calls Gemini enrichment for a set of test players and produces a markdown
report measuring field-fill rate, source-URL presence, consistency, and
grounding metadata quality.

Requires GEMINI_API_KEY in environment or .env file.

Usage:
    python scripts/audit_grounding_quality.py --players 5 --attempts 3
    python scripts/audit_grounding_quality.py --players 1 --attempts 1 --output report.md
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from grounding_quality_metrics import (  # noqa: E402
    GroundingQualityReport,
    compute_consistency_score,
    score_enrichment_result,
)
from llm.client import GroundingMetadataResult  # noqa: E402
from llm.gemini_client import GeminiLLMClient  # noqa: E402
from missing_input_enrichment import GeminiMissingInputEnrichmentProvider  # noqa: E402

_BASKETBALL_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "points": ("minutes_proj", "usage_rate", "points_avg", "points_last5"),
    "rebounds": ("minutes_proj", "usage_rate", "rebound_avg", "rebound_last5"),
    "assists": ("minutes_proj", "usage_rate", "assist_avg", "assist_last5"),
    "threes": (
        "minutes_proj",
        "usage_rate",
        "threes_avg",
        "threes_last5",
        "three_point_attempts",
    ),
}

_TEST_PLAYERS = [
    {"name": "Karl-Anthony Towns", "team": "NYK", "opp": "SAS"},
    {"name": "Jalen Brunson", "team": "NYK", "opp": "SAS"},
    {"name": "Victor Wembanyama", "team": "SAS", "opp": "NYK"},
    {"name": "Devin Vassell", "team": "SAS", "opp": "NYK"},
    {"name": "Stephon Castle", "team": "SAS", "opp": "NYK"},
]


def _build_provider() -> GeminiMissingInputEnrichmentProvider:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set. Add it to .env or environment.", file=sys.stderr)
        sys.exit(1)
    client = GeminiLLMClient(api_key=api_key, model="gemini-2.5-flash", search_grounding=True)
    return GeminiMissingInputEnrichmentProvider(client=client, model="gemini-2.5-flash")


def _run_single_enrichment(
    provider: GeminiMissingInputEnrichmentProvider,
    player: dict[str, str],
    temperature: float | None,
) -> tuple[dict | None, GroundingMetadataResult | None]:
    """Run a single enrichment attempt for one player."""
    from llm.client import LLMError

    all_fields = []
    for fields in _BASKETBALL_REQUIRED_FIELDS.values():
        for f in fields:
            if f not in all_fields:
                all_fields.append(f)

    missing_fields = [f"player:{player['name']}:{f}" for f in all_fields]

    try:
        result = provider.enrich_missing_inputs(
            sport="basketball",
            home_team=player["team"],
            away_team=player["opp"],
            match_date=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            league="nba",
            requested_markets=("points", "rebounds", "assists", "threes"),
            missing_fields=missing_fields,
            players=[{"player_name": player["name"], "team": player["team"], "position": "Unknown"}],
            lines={},
            game={},
        )
    except LLMError as exc:
        print(f"    WARNING: attempt failed: {exc}", file=sys.stderr)
        return None, None

    grounding_metadata = provider.last_grounding_metadata
    return result, grounding_metadata


def _run_audit(
    num_players: int, num_attempts: int
) -> tuple[list[dict], list[list[dict | None]]]:
    """Run enrichment for players and collect results."""
    provider = _build_provider()
    players = _TEST_PLAYERS[:num_players]
    temperatures = [None, 0.7, 1.0][:num_attempts]

    all_reports: list[dict] = []
    all_raw_results: list[list[dict | None]] = []

    for player in players:
        print(f"  Auditing {player['name']}...", file=sys.stderr)
        player_results: list[dict | None] = []
        player_reports: list[GroundingQualityReport] = []

        for temp in temperatures:
            result, metadata = _run_single_enrichment(provider, player, temp)
            player_results.append(result)

            if result:
                report = score_enrichment_result(
                    result, _BASKETBALL_REQUIRED_FIELDS, grounding_metadata=metadata
                )
                player_reports.append(report)

        consistency = compute_consistency_score([r for r in player_results if r])

        all_reports.append({
            "player": player["name"],
            "reports": player_reports,
            "consistency": consistency,
            "raw_results": player_results,
        })
        all_raw_results.append(player_results)

    return all_reports, all_raw_results


def _generate_markdown(reports: list[dict], num_attempts: int) -> str:
    """Generate the markdown audit report."""
    lines: list[str] = []
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines.append("# Grounding Quality Baseline — Basketball Enrichment")
    lines.append("")
    lines.append(f"**Date:** {now}")
    lines.append("**Model:** gemini-2.5-flash")
    lines.append(f"**Players tested:** {len(reports)}")
    lines.append(f"**Attempts per player:** {num_attempts}")
    lines.append("")

    all_fill_rates: list[float] = []
    all_source_rates: list[float] = []
    all_null_rates: list[float] = []
    all_source_counts: list[int] = []
    all_query_counts: list[int] = []

    for entry in reports:
        for r in entry["reports"]:
            all_fill_rates.append(r.field_fill_rate)
            all_source_rates.append(r.source_url_presence_rate)
            all_null_rates.append(r.critical_null_rate)
            all_source_counts.append(r.grounding_source_count)
            all_query_counts.append(r.web_search_query_count)

    lines.append("## Summary Metrics")
    lines.append("")
    lines.append("| Metric | Mean | Min | Max |")
    lines.append("|--------|------|-----|-----|")

    def _row(name: str, values: list[float | int], pct: bool = False) -> str:
        if not values:
            return f"| {name} | N/A | N/A | N/A |"
        fmt = ".1%" if pct else ".1f"
        mean = statistics.mean(values)
        mn = min(values)
        mx = max(values)
        if pct:
            return f"| {name} | {mean:{fmt}} | {mn:{fmt}} | {mx:{fmt}} |"
        return f"| {name} | {mean:{fmt}} | {mn:{fmt}} | {mx:{fmt}} |"

    lines.append(_row("Field-fill rate", all_fill_rates, pct=True))
    lines.append(_row("Source-URL presence", all_source_rates, pct=True))
    lines.append(_row("Critical-null rate", all_null_rates, pct=True))
    lines.append(_row("Grounding sources/call", [float(x) for x in all_source_counts]))
    lines.append(_row("Web search queries/call", [float(x) for x in all_query_counts]))
    lines.append("")

    lines.append("## Per-Player Results")
    lines.append("")
    lines.append("| Player | Fill Rate | Source URLs | Critical Nulls | Confidence | Consistency (CV) |")
    lines.append("|--------|-----------|------------|----------------|------------|------------------|")

    for entry in reports:
        player = entry["player"]
        player_reports: list[GroundingQualityReport] = entry["reports"]
        consistency = entry["consistency"]

        if player_reports:
            avg_fill = statistics.mean(r.field_fill_rate for r in player_reports)
            avg_source = statistics.mean(r.source_url_presence_rate for r in player_reports)
            avg_null = statistics.mean(r.critical_null_rate for r in player_reports)
            avg_conf = statistics.mean(r.confidence_score for r in player_reports)
            lines.append(
                f"| {player} | {avg_fill:.1%} | {avg_source:.1%} | {avg_null:.1%} "
                f"| {avg_conf:.2f} | {consistency:.3f} |"
            )
        else:
            lines.append(f"| {player} | FAILED | FAILED | FAILED | FAILED | N/A |")

    lines.append("")

    lines.append("## Grounding Sources Observed")
    lines.append("")
    all_urls: set[str] = set()
    for entry in reports:
        for result in entry["raw_results"]:
            if not result:
                continue
            for player_data in result.get("players", []):
                for source in player_data.get("sources", []):
                    url = source.get("url", "")
                    if url:
                        all_urls.add(url)
            for source in result.get("sources", []):
                url = source.get("url", "")
                if url:
                    all_urls.add(url)

    if all_urls:
        domains: dict[str, int] = {}
        for url in all_urls:
            try:
                domain = url.split("//")[1].split("/")[0]
                domains[domain] = domains.get(domain, 0) + 1
            except (IndexError, AttributeError):
                continue

        lines.append("**Domains cited:**")
        for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
            lines.append(f"- `{domain}` ({count})")
    else:
        lines.append("- No source URLs observed in enrichment responses")

    lines.append("")
    lines.append("## Bible-Expected Sources (Present / Missing)")
    lines.append("")
    expected = ["espn.com", "statmuse.com", "nba.com", "basketball-reference.com"]
    for source in expected:
        found = any(source in url for url in all_urls)
        status = "PRESENT" if found else "MISSING"
        lines.append(f"- `{source}` — {status}")

    lines.append("")
    lines.append("## Observations")
    lines.append("")
    lines.append("_Fill in after reviewing the data above._")
    lines.append("")

    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit basketball enrichment grounding quality."
    )
    parser.add_argument(
        "--players",
        type=int,
        default=5,
        choices=range(1, 6),
        help="Number of test players (1-5, default: 5)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        choices=range(1, 4),
        help="Enrichment attempts per player (1-3, default: 3)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path for markdown report (default: stdout)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    print(f"Running grounding quality audit: {args.players} players, {args.attempts} attempts each", file=sys.stderr)
    reports, _ = _run_audit(args.players, args.attempts)

    markdown = _generate_markdown(reports, args.attempts)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        print(f"Report written to {output_path}", file=sys.stderr)
    else:
        print(markdown)


if __name__ == "__main__":
    main()
