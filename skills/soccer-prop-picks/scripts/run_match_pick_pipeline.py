#!/usr/bin/env python3
"""Run the full soccer prop pick flow from one CLI command."""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone

from collect_match_inputs import MatchInputRequest, collect_inputs
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
    """Parse '<home> - <away> <date>' into normalized components."""
    text = match_query.strip()
    pattern = re.compile(r"^(?P<home>.+?)\s*-\s*(?P<away>.+?)\s+(?P<date>today|tomorrow|\d{4}-\d{2}-\d{2})$", re.IGNORECASE)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run soccer prop pick pipeline for a match query.")
    parser.add_argument("match_query", help="Match query like 'juve - milan today'")
    parser.add_argument("--top-n", type=int, default=5, help="Number of picks to render")
    args = parser.parse_args()

    parsed = parse_match_query(args.match_query)
    match_inputs = collect_inputs(
        MatchInputRequest(
            home_team=parsed.home_team,
            away_team=parsed.away_team,
            match_date=parsed.match_date,
            competition="League",
        )
    )

    scored_payload = score_props(match_inputs=match_inputs, include_trace=True)
    report = render_report(
        scored_props=scored_payload["scores"],
        match_inputs=match_inputs,
        availability_data={},
        top_n=args.top_n,
        trace=scored_payload["trace"],
    )
    print(report)


if __name__ == "__main__":
    main()
