#!/usr/bin/env python3
"""Run the full soccer prop pick flow from one CLI command."""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone

from collect_match_inputs import MatchInputRequest, collect_inputs
from pipeline_service import run_pipeline
from render_pick_report import render_report
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


_SUPPORTED_TEAMS = {
    "arsenal",
    "liverpool",
    "juve",
    "milan",
    "real madrid",
    "barcelona",
}
_MIN_TOP_N = 1
_MAX_TOP_N = 5


def _normalize_team_name(raw_team: str) -> str:
    parts = [part for part in raw_team.strip().split() if part]
    if not parts:
        raise ValueError("Team name cannot be empty")
    team = " ".join(part.capitalize() for part in parts)
    if team.lower() not in _SUPPORTED_TEAMS:
        raise ValueError(
            "Unknown teams in query. Supported examples include: juve, milan, arsenal, liverpool."
        )
    return team


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
    """Parse '<home> - <away> <date>' into normalized components."""
    text = match_query.strip()
    pattern = re.compile(r"^(?P<home>.+?)\s*-\s*(?P<away>.+?)\s+(?P<date>\S+)$", re.IGNORECASE)
    match = pattern.match(text)
    if not match:
        raise ValueError(
            "Invalid match query format. Expected e.g. 'juve - milan today' or 'juve - milan 2026-05-03'."
        )

    return ParsedMatchQuery((
        _normalize_team_name(match.group("home")),
        _normalize_team_name(match.group("away")),
        _normalize_match_date(match.group("date")),
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
    return parser.parse_args(argv)


def build_dependency_bundle() -> dict[str, object]:
    return {
        "parse_match_query": parse_match_query,
        "build_match_input_request": lambda *, parsed, competition: MatchInputRequest(
            home_team=parsed.home_team,
            away_team=parsed.away_team,
            match_date=parsed.match_date,
            competition=competition,
        ),
        "collect_inputs": collect_inputs,
        "score_props": score_props,
        "render_report": render_report,
    }


def main(argv: list[str] | None = None) -> None:
    args = parse_cli_args(argv)
    deps = build_dependency_bundle()
    report = run_pipeline(
        request={"match_query": args.match_query, "top_n": args.top_n},
        deps=deps,
    )
    print(report)


if __name__ == "__main__":
    main()
