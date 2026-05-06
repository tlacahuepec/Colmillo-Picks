#!/usr/bin/env python3
"""Run the full soccer prop pick flow from one CLI command."""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timedelta, timezone

from api_football_provider import ApiFootballFixtureProvider, ApiFootballOddsSnapshotProvider
from collect_match_inputs import MatchInputRequest, collect_inputs
from llm_fixture_provider import LLMFixtureProvider
from llm.provider_adapter import build_enrich_with_llm
from pipeline_service import PipelineServiceError, run_pipeline
from render_pick_report import render_report
from provider_config import ApiFootballProviderConfig, LLMFixtureProviderConfig
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
_SUPPORTED_FIXTURE_PROVIDERS = {"api-football", "llm", "auto"}


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


<<<<<<< HEAD
def _fixture_provider_source(raw_value: str | None) -> str:
    source = (_optional_cli_value(raw_value) or _optional_cli_value(os.getenv("SOCCER_FIXTURE_PROVIDER")) or "api-football").lower()
    if source not in _SUPPORTED_FIXTURE_PROVIDERS:
        supported = ", ".join(sorted(_SUPPORTED_FIXTURE_PROVIDERS))
        raise ValueError(f"Unsupported fixture provider '{source}'. Supported values: {supported}.")
    return source


=======
>>>>>>> main
def _cli_season(raw_value: str) -> str:
    value = raw_value.strip()
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("season must be a four-digit year") from exc
    if parsed < 1900 or parsed > 2200:
        raise argparse.ArgumentTypeError("season must be a four-digit year")
    return str(parsed)


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
    parser.add_argument(
        "--league",
        default=None,
        help="Optional competition name hint/display value, e.g. 'Premier League'.",
    )
    parser.add_argument(
        "--league-id",
        default=None,
        help="Optional API-Football league ID hint.",
    )
    parser.add_argument(
        "--season",
        type=_cli_season,
        default=None,
        help="Optional API-Football season hint, e.g. 2025.",
    )
    parser.add_argument(
        "--allow-deterministic-fallback",
        action="store_true",
<<<<<<< HEAD
        help="Use deterministic fallback data when fixture lookup fails.",
    )
    parser.add_argument(
        "--fixture-provider",
        choices=sorted(_SUPPORTED_FIXTURE_PROVIDERS),
        default=None,
        help=(
            "Fixture lookup source. Defaults to SOCCER_FIXTURE_PROVIDER or api-football. "
            "Use llm for OpenAI/Grok/openai-compatible fixture lookup."
        ),
    )
    parser.add_argument(
        "--fixture-llm-provider",
        default=None,
        help="Fixture LLM provider hint (openai, xai, or openai-compatible).",
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
=======
        help="Use deterministic fallback data when API-Football fixture lookup fails.",
>>>>>>> main
    )

    args = parser.parse_args(argv)
    if args.use_llm and not args.llm_provider:
        parser.error("--llm-provider is required when --use-llm is set.")
    args.league = _optional_cli_value(args.league)
    args.league_id = _optional_cli_value(args.league_id)
<<<<<<< HEAD
    args.fixture_provider = _optional_cli_value(args.fixture_provider)
    args.fixture_llm_provider = _optional_cli_value(args.fixture_llm_provider)
    args.fixture_llm_model = _optional_cli_value(args.fixture_llm_model)
    args.fixture_llm_base_url = _optional_cli_value(args.fixture_llm_base_url)
=======
>>>>>>> main
    return args




<<<<<<< HEAD
def _build_llm_fixture_provider(
    *,
    fixture_llm_provider: str | None,
    fixture_llm_model: str | None,
    fixture_llm_base_url: str | None,
) -> LLMFixtureProvider:
    config = LLMFixtureProviderConfig.from_env(
        provider=fixture_llm_provider,
        model=fixture_llm_model,
        base_url=fixture_llm_base_url,
    )
    return LLMFixtureProvider(config=config)


=======
>>>>>>> main
def build_dependency_bundle(
    *,
    use_llm: bool,
    llm_provider: str | None,
    llm_model: str | None,
    allow_deterministic_fallback: bool = False,
    league: str | None = None,
    league_id: str | None = None,
    season: str | None = None,
<<<<<<< HEAD
    fixture_provider_name: str | None = None,
    fixture_llm_provider: str | None = None,
    fixture_llm_model: str | None = None,
    fixture_llm_base_url: str | None = None,
) -> dict[str, object]:
    source = _fixture_provider_source(fixture_provider_name)
    api_football_config = ApiFootballProviderConfig.from_env()
    fixture_provider = None
    odds_provider = None

    if source == "llm":
        fixture_provider = _build_llm_fixture_provider(
            fixture_llm_provider=fixture_llm_provider,
            fixture_llm_model=fixture_llm_model,
            fixture_llm_base_url=fixture_llm_base_url,
        )
    elif source == "auto":
        llm_config = LLMFixtureProviderConfig.from_env(
            provider=fixture_llm_provider,
            model=fixture_llm_model,
            base_url=fixture_llm_base_url,
        )
        if llm_config.is_configured():
            fixture_provider = LLMFixtureProvider(config=llm_config)
        elif api_football_config.api_key:
            fixture_provider = ApiFootballFixtureProvider(config=api_football_config)
        elif not allow_deterministic_fallback:
            api_football_config.validate()
    elif api_football_config.api_key:
        fixture_provider = ApiFootballFixtureProvider(config=api_football_config)
    elif not allow_deterministic_fallback:
        api_football_config.validate()

    if api_football_config.api_key:
        odds_provider = ApiFootballOddsSnapshotProvider(config=api_football_config)

=======
) -> dict[str, object]:
    api_football_config = ApiFootballProviderConfig.from_env()
    fixture_provider = None
    odds_provider = None
    if api_football_config.api_key:
        fixture_provider = ApiFootballFixtureProvider(config=api_football_config)
        odds_provider = ApiFootballOddsSnapshotProvider(config=api_football_config)
    elif not allow_deterministic_fallback:
        api_football_config.validate()

>>>>>>> main
    competition_hint = _optional_cli_value(league)

    return {
        "parse_match_query": parse_match_query,
        "build_match_input_request": lambda *, parsed, competition: MatchInputRequest(
            home_team=parsed.home_team,
            away_team=parsed.away_team,
            match_date=parsed.match_date,
            competition=competition_hint or competition,
            competition_hints=[competition_hint] if competition_hint else None,
            league_id=league_id,
            season=season,
        ),
        "collect_inputs": lambda request: collect_inputs(
            request,
            fixture_provider=fixture_provider,
            odds_provider=odds_provider,
            allow_fixture_fallback=allow_deterministic_fallback,
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
            allow_deterministic_fallback=args.allow_deterministic_fallback,
            league=args.league,
            league_id=args.league_id,
            season=args.season,
<<<<<<< HEAD
            fixture_provider_name=getattr(args, "fixture_provider", None),
            fixture_llm_provider=getattr(args, "fixture_llm_provider", None),
            fixture_llm_model=getattr(args, "fixture_llm_model", None),
            fixture_llm_base_url=getattr(args, "fixture_llm_base_url", None),
=======
>>>>>>> main
        )
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    try:
        report = run_pipeline(
            request={
                "match_query": args.match_query,
                "top_n": args.top_n,
                "use_llm": args.use_llm,
                "llm_provider": args.llm_provider,
                "llm_model": args.llm_model,
                "competition": args.league or "League",
            },
            deps=deps,
        )
    except PipelineServiceError as exc:
        cause = exc.__cause__
        message = str(cause) if cause else str(exc)
        raise SystemExit(f"Error: {message}") from exc
    print(report)


if __name__ == "__main__":
    main()
