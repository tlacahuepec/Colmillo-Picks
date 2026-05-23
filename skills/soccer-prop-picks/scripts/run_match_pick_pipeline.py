#!/usr/bin/env python3
"""Run the full soccer prop pick flow from one CLI command."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone

from collect_match_inputs import MatchInputRequest, collect_inputs
from dependency_bundle import (
    _SUPPORTED_FIXTURE_PROVIDERS,
    build_dependency_bundle,
)
from llm_fixture_provider import LLMFixtureProvider
from llm.provider_adapter import build_enrich_with_llm
from pipeline_service import PipelineServiceError, run_pipeline, run_pipeline_with_payload
from render_pick_report import render_report
from provider_config import LLMFixtureProviderConfig
from run_ledger import InMemoryRunLedger, SqliteRunLedger
from score_player_props import score_props

__all__ = [
    "LLMFixtureProvider",
    "LLMFixtureProviderConfig",
    "MatchInputRequest",
    "PipelineServiceError",
    "build_dependency_bundle",
    "build_enrich_with_llm",
    "collect_inputs",
    "main",
    "parse_cli_args",
    "parse_match_query",
    "render_report",
    "run_pipeline",
    "score_props",
]


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


def _optional_cli_value(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    return value or None


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
        help="LLM provider to use when --use-llm is set (supported: gemini, openai, grok).",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="Model name for the selected LLM provider.",
    )
    parser.add_argument(
        "--league",
        default=None,
        help="Optional competition name hint/display value, e.g. 'Premier League'.",
    )
    parser.add_argument(
        "--allow-deterministic-fallback",
        action="store_true",
        help="Use deterministic fallback data when fixture lookup fails.",
    )
    parser.add_argument(
        "--fixture-provider",
        choices=sorted(_SUPPORTED_FIXTURE_PROVIDERS),
        default=None,
        help=(
            "Fixture lookup source. Defaults to SOCCER_FIXTURE_PROVIDER or llm."
        ),
    )
    parser.add_argument(
        "--fixture-llm-provider",
        default=None,
        help="Fixture LLM provider hint (gemini, openai, xai).",
    )
    parser.add_argument(
        "--fixture-llm-model",
        default=None,
        help="Fixture LLM model name. Can also be set with SOCCER_FIXTURE_LLM_MODEL.",
    )
    parser.add_argument(
        "--fixture-llm-base-url",
        default=None,
        help="OpenAI-compatible fixture LLM base URL. Can also be set with SOCCER_FIXTURE_LLM_BASE_URL.",
    )

    args = parser.parse_args(argv)
    if args.use_llm and not args.llm_provider:
        parser.error("--llm-provider is required when --use-llm is set.")
    args.league = _optional_cli_value(args.league)
    args.fixture_provider = _optional_cli_value(args.fixture_provider)
    args.fixture_llm_provider = _optional_cli_value(args.fixture_llm_provider)
    args.fixture_llm_model = _optional_cli_value(args.fixture_llm_model)
    args.fixture_llm_base_url = _optional_cli_value(args.fixture_llm_base_url)
    return args


def _build_ledger():
    try:
        return SqliteRunLedger()
    except Exception:
        print("Warning: could not initialize run ledger, using in-memory fallback.", file=sys.stderr)
        return InMemoryRunLedger()


def main(argv: list[str] | None = None) -> None:
    args = parse_cli_args(argv)
    ledger = _build_ledger()

    request_dict = {
        "match_query": args.match_query,
        "top_n": args.top_n,
        "use_llm": args.use_llm,
        "llm_provider": args.llm_provider,
        "llm_model": args.llm_model,
        "competition": args.league or "League",
    }
    run_ctx = ledger.start_run(source="cli", request=request_dict)

    try:
        deps = build_dependency_bundle(
            use_llm=args.use_llm,
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
            allow_deterministic_fallback=args.allow_deterministic_fallback,
            league=args.league,
            fixture_provider_name=getattr(args, "fixture_provider", None),
            fixture_llm_provider=getattr(args, "fixture_llm_provider", None),
            fixture_llm_model=getattr(args, "fixture_llm_model", None),
            fixture_llm_base_url=getattr(args, "fixture_llm_base_url", None),
        )
    except ValueError as exc:
        ledger.fail_run(run_ctx.id, error_summary=str(exc), error_stage="config")
        raise SystemExit(f"Error: {exc}") from exc
    try:
        result = run_pipeline_with_payload(request=request_dict, deps=deps)
    except PipelineServiceError as exc:
        cause = exc.__cause__
        message = str(cause) if cause else str(exc)
        ledger.fail_run(run_ctx.id, error_summary=message, error_stage=exc.stage)
        raise SystemExit(f"Error: {message}") from exc

    for step in result.get("steps", []):
        ledger.record_step(run_ctx.id, step["name"], status=step["status"], duration_ms=step["duration_ms"])

    failed_steps = [s for s in result.get("steps", []) if s["status"] == "failed"]
    if failed_steps:
        reasons = [f"{s['name']} failed" for s in failed_steps]
        ledger.partial_run(run_ctx.id, reasons=reasons)
    else:
        ledger.complete_run(run_ctx.id)
    print(result["report_markdown"])


if __name__ == "__main__":
    main()
