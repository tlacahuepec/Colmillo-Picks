"""Tests for Best Today page helper functions."""

from __future__ import annotations

from services.ui.best_today_helpers import (
    build_availability_batch_payload,
    build_slate_payload,
    clear_slate_cache,
    confidence_color,
    format_kickoff_local,
    format_risk_flags_markdown,
    format_slate_candidate_row,
    format_slate_list_item,
    format_match_run_summary,
    format_source_pick_detail,
    format_token_summary,
    match_badges_to_candidates,
    render_no_candidates_message,
    render_partial_failure_summary,
    should_render_cached_slate,
    slate_status_icon,
    store_slate_result,
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


class TestSessionStateCaching:
    def test_store_slate_result_sets_key(self) -> None:
        session = {}
        detail = {"id": "abc", "status": "success", "candidates": []}

        store_slate_result(session, detail)

        assert session["last_slate_detail"] == detail

    def test_clear_slate_cache_removes_key(self) -> None:
        session = {"last_slate_detail": {"id": "abc"}}

        clear_slate_cache(session)

        assert "last_slate_detail" not in session

    def test_clear_slate_cache_no_op_when_empty(self) -> None:
        session = {}

        clear_slate_cache(session)

        assert "last_slate_detail" not in session

    def test_should_render_cached_returns_false_when_empty(self) -> None:
        session = {}

        assert should_render_cached_slate(session) is False

    def test_should_render_cached_returns_true_when_present(self) -> None:
        session = {"last_slate_detail": {"id": "abc", "status": "success"}}

        assert should_render_cached_slate(session) is True


class TestConfidenceColor:
    def test_high_is_green(self) -> None:
        assert confidence_color("high") == "green"

    def test_medium_is_orange(self) -> None:
        assert confidence_color("medium") == "orange"

    def test_low_is_red(self) -> None:
        assert confidence_color("low") == "red"

    def test_unknown_defaults_to_gray(self) -> None:
        assert confidence_color("unknown") == "gray"

    def test_case_insensitive(self) -> None:
        assert confidence_color("HIGH") == "green"


class TestFormatRiskFlagsMarkdown:
    def test_empty_list_returns_empty_string(self) -> None:
        assert format_risk_flags_markdown([]) == ""

    def test_single_flag(self) -> None:
        result = format_risk_flags_markdown(["missing_data"])
        assert "missing_data" in result

    def test_multiple_flags(self) -> None:
        result = format_risk_flags_markdown(["missing_data", "low_sample"])
        assert "missing_data" in result
        assert "low_sample" in result


class TestBuildAvailabilityBatchPayload:
    def test_extracts_player_market_line(self) -> None:
        candidates = [
            {"rank": 1, "player": "Saka", "market": "passes", "line": 50.5, "direction": "over"},
            {"rank": 2, "player": "LeBron", "market": "points", "line": 25.5, "direction": "over"},
        ]

        payload = build_availability_batch_payload(candidates)

        assert payload == [
            {"player": "Saka", "market": "passes", "line": 50.5},
            {"player": "LeBron", "market": "points", "line": 25.5},
        ]

    def test_skips_candidates_without_player(self) -> None:
        candidates = [
            {"rank": 1, "player": "", "market": "passes", "line": 50.5},
            {"rank": 2, "player": "Saka", "market": "passes", "line": 50.5},
        ]

        payload = build_availability_batch_payload(candidates)

        assert len(payload) == 1
        assert payload[0]["player"] == "Saka"

    def test_handles_none_line(self) -> None:
        candidates = [{"rank": 1, "player": "Saka", "market": "passes", "line": None}]

        payload = build_availability_batch_payload(candidates)

        assert payload[0]["line"] == 0.0


class TestMatchBadgesToCandidates:
    def test_maps_by_player_and_market(self) -> None:
        badges = [
            {"player": "Saka", "market": "passes", "status": "available", "platform": "prizepicks"},
            {"player": "LeBron", "market": "points", "status": "unavailable", "platform": "prizepicks"},
        ]
        candidates = [
            {"rank": 1, "player": "Saka", "market": "passes"},
            {"rank": 2, "player": "LeBron", "market": "points"},
        ]

        result = match_badges_to_candidates(badges, candidates)

        assert result[0]["status"] == "available"
        assert result[1]["status"] == "unavailable"

    def test_returns_none_for_unmatched_candidates(self) -> None:
        badges = [
            {"player": "Saka", "market": "passes", "status": "available", "platform": "prizepicks"},
        ]
        candidates = [
            {"rank": 1, "player": "Saka", "market": "passes"},
            {"rank": 2, "player": "LeBron", "market": "points"},
        ]

        result = match_badges_to_candidates(badges, candidates)

        assert result[0]["status"] == "available"
        assert result.get(1) is None

    def test_empty_badges_returns_empty_dict(self) -> None:
        result = match_badges_to_candidates([], [{"rank": 1, "player": "Saka", "market": "passes"}])

        assert result == {}


class TestFormatSourcePickDetail:
    def test_returns_empty_string_for_empty_dict(self) -> None:
        assert format_source_pick_detail({}) == ""

    def test_formats_reasoning(self) -> None:
        source_pick = {
            "llm_rationale": "Strong recent form with 55+ passes in last 3 games.",
            "score": 0.85,
            "factors": {"recent_form": 0.9, "matchup": 0.8},
        }

        result = format_source_pick_detail(source_pick)

        assert "Strong recent form" in result
        assert "0.85" in result

    def test_formats_factors(self) -> None:
        source_pick = {
            "factors": {"recent_form": 0.9, "venue": 0.7, "matchup": 0.8},
        }

        result = format_source_pick_detail(source_pick)

        assert "recent_form" in result
        assert "0.9" in result

    def test_handles_missing_fields_gracefully(self) -> None:
        source_pick = {"score": 0.5}

        result = format_source_pick_detail(source_pick)

        assert "0.5" in result


class TestFormatKickoffLocal:
    def test_valid_utc_string_returns_local_time(self) -> None:
        result = format_kickoff_local("2026-06-04T19:30:00Z")

        assert result != "—"
        assert "Jun" in result or "06" in result
        assert ":" in result

    def test_none_returns_dash(self) -> None:
        assert format_kickoff_local(None) == "—"

    def test_invalid_string_returns_dash(self) -> None:
        assert format_kickoff_local("not-a-date") == "—"

    def test_empty_string_returns_dash(self) -> None:
        assert format_kickoff_local("") == "—"

    def test_iso_format_without_z_suffix(self) -> None:
        result = format_kickoff_local("2026-06-04T19:30:00+00:00")

        assert result != "—"
        assert ":" in result


class TestFormatTokenSummary:
    def test_all_values(self) -> None:
        result = format_token_summary(5000, 1500, 6500)

        assert "5,000 prompt" in result
        assert "1,500 completion" in result
        assert "6,500 total" in result

    def test_none_total_returns_empty(self) -> None:
        assert format_token_summary(100, 50, None) == ""

    def test_only_total(self) -> None:
        result = format_token_summary(None, None, 6500)

        assert "6,500 total" in result
        assert "prompt" not in result


class TestSlateStatusIcon:
    def test_success(self) -> None:
        assert slate_status_icon("success") == "\u2705"

    def test_failed(self) -> None:
        assert slate_status_icon("failed") == "\u274c"

    def test_pending(self) -> None:
        assert slate_status_icon("pending") == "\u23f3"

    def test_unknown_returns_question_mark(self) -> None:
        assert slate_status_icon("weird") == "\u2753"


class TestFormatSlateListItem:
    def test_formats_complete_item(self) -> None:
        slate = {
            "id": "abc-123",
            "status": "success",
            "request": {"date": "2026-06-01", "sports": ["soccer", "basketball"]},
            "latency_ms": 3000,
        }

        result = format_slate_list_item(slate)

        assert "2026-06-01" in result
        assert "soccer" in result
        assert "success" in result
        assert "3000ms" in result

    def test_formats_pending_item(self) -> None:
        slate = {
            "id": "def-456",
            "status": "pending",
            "request": {"date": "2026-06-02", "sports": ["baseball"]},
            "latency_ms": None,
        }

        result = format_slate_list_item(slate)

        assert "2026-06-02" in result
        assert "pending" in result
