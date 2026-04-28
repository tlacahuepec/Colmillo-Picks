#!/usr/bin/env python3
"""Run the full soccer prop pick flow from one CLI command."""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone

from api_football_provider import ApiFootballFixtureProvider, ApiFootballOddsSnapshotProvider
from collect_match_inputs import MatchInputRequest, collect_inputs
from llm.provider_adapter import build_enrich_with_llm
from pipeline_service import run_pipeline
from render_pick_report import render_report
from provider_config import ApiFootballProviderConfig
from score_player_props import score_props


class ParsedMatchQuery(tuple):
    __slots__ = ()

    @property
    def home_team(self) -> str:
        return self[0]

    @property
    def away_team(self) -> str:
        return self[1]

    @property
    def match_date(self) -> str:
        return self[2]


_MIN_TOP_N = 1
_MAX_TOP_N = 5


def _normalize_team_name(raw_team: str) -> str:
    parts = [part for part in raw_team.strip().split() if part]
    if not parts:
        raise ValueError("Team name cannot be empty")
    return " ".join(part.capitalize() for part in parts)


def _normalize_match_date(raw_date: str) -> str:
    token = raw_date.strip().lower()
    today = datetime.now(timezone.utc).date()
    if token == "today":
        return today.isoformat()
    if token == "tomorrow":
        return (today + timedelta(days=1)).isoformat()

    try:
        return datetime.strptime(raw_date.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError(
            "Invalid match date. Use 'today', 'tomorrow', or YYYY-MM-DD format."
        ) from exc


def parse_match_query(match_query: str) -> ParsedMatchQuery:
    """Parse free-form match query into normalized components."""
    text = match_query.strip()
    date_pattern = re.compile(r"\b(today|tomorrow|\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)
    date_match = date_pattern.search(text)
    if not date_match:
        raise ValueError(
            "Invalid match date. Use 'today', 'tomorrow', or YYYY-MM-DD format."
        )
    date_token = date_match.group(1)

    teams_text = (text[: date_match.start()] + text[date_match.end() :]).strip(" ,;")
    teams_text = re.sub(r"\b(for|on)\s*$", "", teams_text, flags=re.IGNORECASE).strip()
    team_parts: tuple[str, str] | None = None
    for separator_pattern in (r"\s*-\s*", r"\s+vs\.?\s+", r"\s+v\.?\s+"):
        parts = re.split(separator_pattern, teams_text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            team_parts = (parts[0], parts[1])
            break

    if not team_parts:
        raise ValueError(
            "Invalid match query format. Expected teams separated by '-', 'vs', or 'v'."
        )

    return ParsedMatchQuery((
        _normalize_team_name(team_parts[0]),
        _normalize_team_name(team_parts[1]),
        _normalize_match_date(date_token),
    ))


def _cli_top_n(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("top-n must be an integer") from exc
    if not _MIN_TOP_N <= value <= _MAX_TOP_N:
        raise argparse.ArgumentTypeError("top-n must be a positive integer between 1 and 5")
    return value


def parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run soccer prop pick pipeline for a match query.")
    parser.add_argument("match_query", help="Match query like 'juve - milan today'")
    parser.add_argument(
        "--top-n",
        type=_cli_top_n,
        default=5,
        help="Number of picks to render (1-5)",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable LLM enrichment for the scored picks.",
    )
    parser.add_argument(
        "--llm-provider",
        default=None,
        help="LLM provider to use when --use-llm is set (supported: openai).",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="Model name for the selected LLM provider.",
    )

    args = parser.parse_args(argv)
    if args.use_llm and not args.llm_provider:
        parser.error("--llm-provider is required when --use-llm is set.")
    return args




def build_dependency_bundle(*, use_llm: bool, llm_provider: str | None, llm_model: str | None) -> dict[str, object]:
    api_football_config = ApiFootballProviderConfig.from_env()
    fixture_provider = ApiFootballFixtureProvider(config=api_football_config)
    odds_provider = ApiFootballOddsSnapshotProvider(config=api_football_config)

    return {
        "parse_match_query": parse_match_query,
        "build_match_input_request": lambda *, parsed, competition: MatchInputRequest(
            home_team=parsed.home_team,
            away_team=parsed.away_team,
            match_date=parsed.match_date,
            competition=competition,
        ),
        "collect_inputs": lambda request: collect_inputs(
            request,
            fixture_provider=fixture_provider,
            odds_provider=odds_provider,
        ),
        "score_props": score_props,
        "render_report": render_report,
        "enrich_with_llm": build_enrich_with_llm(
            use_llm=use_llm,
            llm_provider=llm_provider,
            llm_model=llm_model,
        ),
    }


def main(argv: list[str] | None = None) -> None:
    args = parse_cli_args(argv)
    try:
        deps = build_dependency_bundle(
            use_llm=args.use_llm,
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
        )
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    report = run_pipeline(
        request={
            "match_query": args.match_query,
            "top_n": args.top_n,
            "use_llm": args.use_llm,
            "llm_provider": args.llm_provider,
            "llm_model": args.llm_model,
        },
        deps=deps,
    )
    print(report)


if __name__ == "__main__":
    main()
