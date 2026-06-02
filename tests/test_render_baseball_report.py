"""Tests for MLB report renderer with responsible gaming guardrails."""

from __future__ import annotations

from typing import Any

from render_baseball_report import render_baseball_report

BANNED_WORDS = ["guaranteed", "certain", "sure thing", "lock", "certainty"]


def _sample_match_context() -> dict[str, Any]:
    return {
        "home_team": "NYY",
        "away_team": "BOS",
        "venue": "Yankee Stadium",
        "game_time_utc": "2026-05-25T23:05:00Z",
        "home_probable_pitcher": "Gerrit Cole (RHP)",
        "away_probable_pitcher": "Brayan Bello (RHP)",
        "weather": {"temp_f": 78, "wind_mph": 12, "wind_direction": "out to center", "dome": False},
    }


def _sample_picks() -> list[dict[str, Any]]:
    return [
        {
            "player": "Aaron Judge",
            "market": "home_runs",
            "direction": "over",
            "line": 0.5,
            "score": 0.82,
            "confidence": "high",
            "risk_flags": [],
            "top_factors": [
                {"factor": "ballpark_factor", "score": 0.9, "weight": 0.2},
                {"factor": "pitcher_matchup_handedness", "score": 0.62, "weight": 0.18},
            ],
            "explanation": "Judge benefits from favorable ballpark and platoon advantage.",
        },
        {
            "player": "Juan Soto",
            "market": "total_bases",
            "direction": "over",
            "line": 2.5,
            "score": 0.71,
            "confidence": "medium",
            "risk_flags": ["missing_data"],
            "top_factors": [
                {"factor": "recent_form_momentum", "score": 0.75, "weight": 0.15},
            ],
            "explanation": "Soto trending up in recent form.",
        },
    ]


def _sample_no_bet_picks() -> list[dict[str, Any]]:
    return [
        {
            "player": "Rafael Devers",
            "market": "hits",
            "reason": "missing_probable_pitcher",
        },
        {
            "player": "Rafael Devers",
            "market": "total_bases",
            "reason": "stale_odds",
        },
    ]


def _sample_provider_statuses() -> list[dict[str, Any]]:
    return [
        {"provider": "statsapi", "data_type": "stats", "timestamp": "2026-05-25T22:00:00Z", "status": "fresh"},
        {"provider": "statsapi", "data_type": "lineup", "timestamp": "2026-05-25T22:30:00Z", "status": "fresh"},
        {"provider": "openweathermap", "data_type": "weather", "timestamp": "2026-05-25T22:45:00Z", "status": "fresh"},
        {"provider": "odds_api", "data_type": "odds", "timestamp": "2026-05-25T21:00:00Z", "status": "stale"},
    ]


class TestReportStructure:
    def test_renders_non_empty_string(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
        )
        assert isinstance(report, str)
        assert len(report) > 0

    def test_contains_matchup_summary(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
        )
        assert "NYY" in report
        assert "BOS" in report
        assert "Yankee Stadium" in report
        assert "Gerrit Cole" in report

    def test_contains_weather_info(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
        )
        assert "78" in report
        assert "wind" in report.lower()

    def test_contains_picks_table(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
        )
        assert "Aaron Judge" in report
        assert "home_runs" in report
        assert "over" in report.lower()
        assert "high" in report.lower()

    def test_picks_show_confidence_level(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
        )
        assert "High" in report or "high" in report.lower()
        assert "Medium" in report or "medium" in report.lower()

    def test_picks_show_top_risk_factor(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
        )
        assert "missing_data" in report


class TestNoBetSection:
    def test_no_bet_section_present(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
            no_bet_picks=_sample_no_bet_picks(),
        )
        assert "NO-BET" in report or "No-Bet" in report

    def test_no_bet_shows_reason(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
            no_bet_picks=_sample_no_bet_picks(),
        )
        assert "missing_probable_pitcher" in report
        assert "stale_odds" in report

    def test_no_bet_shows_blocked_market(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=[],
            no_bet_picks=_sample_no_bet_picks(),
        )
        assert "hits" in report
        assert "Rafael Devers" in report

    def test_all_no_bet_renders_meaningful_message(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=[],
            no_bet_picks=_sample_no_bet_picks(),
        )
        assert "no actionable picks" in report.lower() or "no picks available" in report.lower()


class TestSourceAudit:
    def test_source_audit_table_present(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
            provider_statuses=_sample_provider_statuses(),
        )
        assert "statsapi" in report
        assert "openweathermap" in report

    def test_source_audit_shows_timestamps(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
            provider_statuses=_sample_provider_statuses(),
        )
        assert "2026-05-25" in report

    def test_source_audit_shows_freshness(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
            provider_statuses=_sample_provider_statuses(),
        )
        assert "fresh" in report.lower() or "stale" in report.lower()


class TestResponsibleGaming:
    def test_disclaimer_present(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
        )
        assert "1-800-522-4700" in report or "ncpgambling.org" in report

    def test_disclaimer_at_bottom(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
        )
        lines = report.strip().split("\n")
        last_section = "\n".join(lines[-5:])
        assert "1-800-522-4700" in last_section or "ncpgambling.org" in last_section

    def test_no_banned_words_in_report(self):
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=_sample_picks(),
            no_bet_picks=_sample_no_bet_picks(),
            provider_statuses=_sample_provider_statuses(),
        )
        report_lower = report.lower()
        import re
        for word in BANNED_WORDS:
            pattern = r"\b" + re.escape(word) + r"\b"
            assert not re.search(pattern, report_lower), f"Banned word '{word}' found in report"


class TestZeroLineFiltering:
    """Defense-in-depth: renderer must never show picks with line=0."""

    def test_zero_line_pick_excluded_from_rendered_table(self) -> None:
        picks = [
            {
                "player": "BadPick",
                "market": "hits",
                "direction": "over",
                "line": 0,
                "score": 0.5,
                "confidence": "low",
                "risk_flags": ["missing_data"],
                "top_factors": [],
                "explanation": "",
            },
            {
                "player": "GoodPick",
                "market": "hits",
                "direction": "over",
                "line": 1.5,
                "score": 0.8,
                "confidence": "high",
                "risk_flags": [],
                "top_factors": [],
                "explanation": "",
            },
        ]
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=picks,
        )
        assert "GoodPick" in report
        assert "BadPick" not in report.split("Recommended Picks")[1].split("NO-BET")[0] if "NO-BET" in report else "BadPick" not in report.split("Recommended Picks")[1]

    def test_all_zero_line_picks_renders_no_picks_message(self) -> None:
        picks = [
            {
                "player": "BadPick",
                "market": "hits",
                "direction": "over",
                "line": 0,
                "score": 0.5,
                "confidence": "low",
                "risk_flags": ["missing_data"],
                "top_factors": [],
                "explanation": "",
            },
        ]
        report = render_baseball_report(
            match_context=_sample_match_context(),
            picks=picks,
        )
        assert "no actionable picks" in report.lower()


class TestBaseballTerminology:
    def test_uses_baseball_terminology(self):
        ctx = _sample_match_context()
        report = render_baseball_report(
            match_context=ctx,
            picks=_sample_picks(),
        )
        report_lower = report.lower()
        assert "pitcher" in report_lower
        assert "goals" not in report_lower
        assert "halves" not in report_lower

    def test_data_quality_section_present(self):
        ctx = _sample_match_context()
        ctx["data_quality"] = {
            "lineup_status": "confirmed",
            "pitcher_status": "confirmed",
            "weather_status": "available",
            "odds_status": "stale",
        }
        report = render_baseball_report(
            match_context=ctx,
            picks=_sample_picks(),
        )
        assert "confirmed" in report.lower() or "data quality" in report.lower()
