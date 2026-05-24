"""CLI for the daily soccer intelligence task.

Usage:
    GEMINI_API_KEY=... python run_daily_intelligence.py
    GEMINI_API_KEY=... python run_daily_intelligence.py --provider gemini --top-n 3 --date 2026-05-21
    XAI_API_KEY=... python run_daily_intelligence.py --provider grok
    python run_daily_intelligence.py --output-json /tmp/briefing.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from daily_intelligence import DailyIntelligenceClient, DailyIntelligenceError


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _parse_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}'. Expected format: YYYY-MM-DD")
    return value


def _parse_top_n(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"--top-n must be an integer, got '{value}'")
    if n < 1 or n > 10:
        raise argparse.ArgumentTypeError(f"--top-n must be between 1 and 10, got {n}")
    return n


def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch today's top soccer matches with injuries, lineups, and odds via LLM."
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        metavar="PROVIDER",
        help="LLM provider to use: gemini, grok, openai (default: COLMILLO_LLM_PROVIDER or gemini)",
    )
    parser.add_argument(
        "--top-n",
        type=_parse_top_n,
        default=5,
        metavar="N",
        help="Number of matches to retrieve (1-10, default 5)",
    )
    parser.add_argument(
        "--date",
        type=_parse_date,
        default=_today_utc(),
        metavar="YYYY-MM-DD",
        help="Date to fetch matches for (default: today UTC)",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write JSON output to this file instead of stdout",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_cli_args(argv)

    try:
        client = DailyIntelligenceClient.from_env(provider=args.provider)
    except DailyIntelligenceError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    try:
        briefing = client.fetch_daily_briefing(date_utc=args.date, top_n=args.top_n)
    except DailyIntelligenceError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    output = json.dumps(briefing, indent=2, ensure_ascii=False)

    if args.output_json is not None:
        args.output_json.write_text(output, encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main(sys.argv[1:])
