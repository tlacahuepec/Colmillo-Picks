from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import REPO_ROOT, load_script_module


def test_parse_match_query_with_today_keyword(
    parsed_query_fixture: str,
    resolved_match_date: str,
) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    parsed = pipeline.parse_match_query(parsed_query_fixture)

    assert parsed.home_team == "Juve"
    assert parsed.away_team == "Milan"
    assert parsed.match_date == resolved_match_date


@pytest.mark.parametrize(
    "query,expected_home,expected_away",
    [
        ("juve-milan today", "Juve", "Milan"),
        ("  juve   -   milan   today  ", "Juve", "Milan"),
        ("Juve - Milan today", "Juve", "Milan"),
    ],
)
def test_parse_match_query_supports_juve_milan_variants(query: str, expected_home: str, expected_away: str) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    parsed = pipeline.parse_match_query(query)

    assert parsed.home_team == expected_home
    assert parsed.away_team == expected_away


def test_parse_match_query_with_tomorrow_keyword() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    parsed = pipeline.parse_match_query("arsenal - liverpool tomorrow")

    assert parsed.home_team == "Arsenal"
    assert parsed.away_team == "Liverpool"
    assert parsed.match_date == (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()


def test_parse_match_query_with_iso_date() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    parsed = pipeline.parse_match_query("juve - milan 2026-05-03")

    assert parsed.home_team == "Juve"
    assert parsed.away_team == "Milan"
    assert parsed.match_date == "2026-05-03"


def test_parse_match_query_rejects_unknown_teams_with_explicit_message() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    with pytest.raises(ValueError, match="Unknown teams in query"):
        pipeline.parse_match_query("teamx - teamy today")


def test_parse_match_query_invalid_date_token_has_explicit_message() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    with pytest.raises(ValueError, match="Invalid match date"):
        pipeline.parse_match_query("juve - milan someday")


def test_pipeline_cli_runs_end_to_end_with_single_command() -> None:
    script = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts" / "run_match_pick_pipeline.py"

    result = subprocess.run(
        [sys.executable, str(script), "juve - milan today", "--top-n", "3"],
        check=True,
        capture_output=True,
        text=True,
    )

    report = result.stdout
    assert "Juve" in report
    assert "Milan" in report
    assert "Top 5 Recommended Picks" in report
    assert "| 1 |" in report
