"""Tests for Best Today page helper functions."""

from __future__ import annotations

from services.ui.best_today_helpers import (
    build_slate_payload,
    format_slate_candidate_row,
    format_match_run_summary,
    render_no_candidates_message,
    render_partial_failure_summary,
)


class TestBuildSlatePayload:
    def test_builds_from_form_inputs(self) -> None:
        payload = build_slate_payload(
            date="2026-06-01",
            sports=["soccer", "basketball"],
            max_matches_per_sport=3,
            top_n=10,
        )

        assert payload == {
            "date": "2026-06-01",
            "sports": ["soccer", "basketball"],
            "max_matches_per_sport": 3,
            "top_n": 10,
        }

    def test_defaults_sports_when_empty(self) -> None:
        payload = build_slate_payload(
            date="2026-06-01",
            sports=[],
            max_matches_per_sport=3,
            top_n=10,
        )

        assert payload["sports"] == ["soccer", "basketball", "baseball"]


class TestFormatSlateCandidateRow:
    def test_formats_candidate_with_all_fields(self) -> None:
        candidate = {
            "rank": 1,
            "sport": "soccer",
            "player": "Saka",
            "market": "passes",
            "line": 50.5,
            "direction": "over",
            "confidence": "high",
            "normalized_score": 90.0,
            "risk_flags": ["missing_data"],
            "availability_status": "unknown",
            "source_match": {"home_team": "Arsenal", "away_team": "Liverpool"},
        }

        row = format_slate_candidate_row(candidate)

        assert "Saka" in row
        assert "passes" in row
        assert "over" in row
        assert "90" in row

    def test_handles_missing_optional_fields(self) -> None:
        candidate = {
            "rank": 1,
            "sport": "basketball",
            "player": "LeBron",
            "market": "points",
            "line": None,
            "direction": "over",
            "confidence": "medium",
            "normalized_score": 70.0,
            "risk_flags": [],
            "availability_status": "unknown",
            "source_match": {},
        }

        row = format_slate_candidate_row(candidate)

        assert "LeBron" in row
        assert "points" in row


class TestFormatMatchRunSummary:
    def test_formats_successful_run(self) -> None:
        run = {
            "sport": "soccer",
            "home_team": "Arsenal",
            "away_team": "Liverpool",
            "event_date": "2026-06-01",
            "status": "success",
            "pick_count": 3,
            "latency_ms": 2000,
        }

        text = format_match_run_summary(run)

        assert "Arsenal" in text
        assert "Liverpool" in text
        assert "success" in text.lower() or "3 picks" in text.lower()

    def test_formats_failed_run(self) -> None:
        run = {
            "sport": "basketball",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "event_date": "2026-06-01",
            "status": "failed",
            "error_stage": "pipeline",
            "error_message": "Provider timeout",
            "pick_count": 0,
        }

        text = format_match_run_summary(run)

        assert "Lakers" in text
        assert "failed" in text.lower()


class TestRenderNoCandidatesMessage:
    def test_returns_message_string(self) -> None:
        message = render_no_candidates_message()

        assert message
        assert "no" in message.lower() or "empty" in message.lower()


class TestRenderPartialFailureSummary:
    def test_shows_failed_matches(self) -> None:
        match_runs = [
            {"sport": "soccer", "home_team": "Arsenal", "away_team": "Liverpool", "status": "success", "pick_count": 2},
            {"sport": "basketball", "home_team": "Lakers", "away_team": "Celtics", "status": "failed", "error_message": "timeout"},
        ]

        text = render_partial_failure_summary(match_runs)

        assert "Lakers" in text
        assert "failed" in text.lower() or "timeout" in text.lower()

    def test_returns_empty_when_no_failures(self) -> None:
        match_runs = [
            {"sport": "soccer", "home_team": "Arsenal", "away_team": "Liverpool", "status": "success", "pick_count": 2},
        ]

        text = render_partial_failure_summary(match_runs)

        assert text == ""
