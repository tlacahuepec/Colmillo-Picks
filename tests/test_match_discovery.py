"""Tests for sport-aware match discovery."""

from __future__ import annotations

import json

import pytest

from llm.client import LLMError
from llm.intelligence_prompt_builder import (
    build_daily_intelligence_user_prompt,
    build_match_discovery_user_prompt,
)
from match_discovery import MatchDiscoveryClient, MatchDiscoveryValidationError


class _FakeLLMClient:
    def __init__(self, responses: dict[str, dict | Exception]) -> None:
        self._responses = responses
        self.calls: list[dict] = []

    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        payload = json.loads(user_prompt)
        sport = payload["sports"][0]
        self.calls.append({
            "sport": sport,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "schema": schema,
        })
        response = self._responses[sport]
        if isinstance(response, Exception):
            raise response
        return response


def _discovery_response(sport: str) -> dict:
    return {
        "schema_version": "v1.0.0",
        "date_utc": "2030-06-01",
        "generated_at_utc": "2030-06-01T12:00:00Z",
        "provider": "fake",
        "model": "fake-model",
        "sports": {
            sport: {
                "matches": [
                    {
                        "home_team": "Arsenal",
                        "away_team": "Liverpool",
                        "event_date": "2030-06-01",
                        "league": "premier_league",
                        "competition": "Premier League",
                        "kickoff_utc": "2030-06-01T19:00:00Z",
                        "importance": "high",
                        "notes": "Title-race leverage",
                        "sources": [
                            {"label": "fixture list", "url": "https://example.com/fixture"}
                        ],
                        "data_quality": {
                            "confidence": "medium",
                            "missing_fields": ["confirmed_lineups"],
                        },
                    }
                ]
            }
        },
    }


def test_match_discovery_prompt_supports_multiple_sports_without_breaking_daily_prompt() -> None:
    raw = build_match_discovery_user_prompt(
        date_utc="2026-06-01",
        sports=["soccer", "basketball"],
        limit_per_sport=3,
    )
    parsed = json.loads(raw)

    assert parsed["sports"] == ["soccer", "basketball"]
    assert parsed["limit_per_sport"] == 3
    assert "grouped_by_sport" in parsed["required_json_shape"]

    daily_shape = json.loads(
        build_daily_intelligence_user_prompt(date_utc="2026-06-01", top_n=5)
    )["required_json_shape"]
    assert "top_matches" in daily_shape


def test_discover_matches_normalizes_grouped_llm_response() -> None:
    fake_llm = _FakeLLMClient({"soccer": _discovery_response("soccer")})
    client = MatchDiscoveryClient(client=fake_llm)

    result = client.discover_matches(
        date_utc="2030-06-01",
        sports=["soccer"],
        limit_per_sport=5,
    )

    match = result["results"]["soccer"]["matches"][0]
    assert match["home_team"] == "Arsenal"
    assert match["away_team"] == "Liverpool"
    assert match["event_date"] == "2030-06-01"
    assert match["source_provider"] == "fake"
    assert match["source_model"] == "fake-model"
    assert match["sources"][0]["label"] == "fixture list"
    assert match["data_quality"]["confidence"] == "medium"


def test_discover_matches_keeps_successful_sports_when_one_provider_call_fails() -> None:
    fake_llm = _FakeLLMClient({
        "soccer": _discovery_response("soccer"),
        "basketball": LLMError("provider timeout"),
    })
    client = MatchDiscoveryClient(client=fake_llm)

    result = client.discover_matches(
        date_utc="2030-06-01",
        sports=["soccer", "basketball"],
        limit_per_sport=2,
    )

    assert result["results"]["soccer"]["matches"]
    assert result["results"]["soccer"]["error"] is None
    assert result["results"]["basketball"]["matches"] == []
    assert "provider timeout" in result["results"]["basketball"]["error"]


def test_discover_matches_validates_sports_and_limit() -> None:
    client = MatchDiscoveryClient(client=_FakeLLMClient({}))

    with pytest.raises(MatchDiscoveryValidationError, match="Unsupported sport"):
        client.discover_matches(date_utc="2026-06-01", sports=["cricket"], limit_per_sport=2)

    with pytest.raises(MatchDiscoveryValidationError, match="limit_per_sport"):
        client.discover_matches(date_utc="2026-06-01", sports=["soccer"], limit_per_sport=6)


def test_discover_matches_filters_out_wrong_date_matches() -> None:
    response = {
        "sports": {
            "soccer": {
                "matches": [
                    {
                        "home_team": "Arsenal",
                        "away_team": "Liverpool",
                        "event_date": "2030-06-01",
                        "kickoff_utc": "2030-06-01T19:00:00Z",
                        "importance": "high",
                    },
                    {
                        "home_team": "Barca",
                        "away_team": "Madrid",
                        "event_date": "2030-06-02",
                        "kickoff_utc": "2030-06-02T20:00:00Z",
                        "importance": "high",
                    },
                    {
                        "home_team": "Bayern",
                        "away_team": "Dortmund",
                        "event_date": "2030-05-31",
                        "kickoff_utc": "2030-05-31T18:00:00Z",
                        "importance": "high",
                    },
                ]
            }
        },
    }
    client = MatchDiscoveryClient(client=_FakeLLMClient({"soccer": response}))

    result = client.discover_matches(date_utc="2030-06-01", sports=["soccer"], limit_per_sport=5)

    matches = result["results"]["soccer"]["matches"]
    assert len(matches) == 1
    assert matches[0]["home_team"] == "Arsenal"


def test_discover_matches_preserves_informational_error_from_llm() -> None:
    """When the LLM returns matches with a per-sport informational note, it is preserved."""
    response = {
        "sports": {
            "soccer": {
                "matches": [
                    {
                        "home_team": "Norway",
                        "away_team": "Sweden",
                        "event_date": "2030-06-01",
                        "kickoff_utc": "2030-06-01T18:00:00Z",
                        "importance": "medium",
                    },
                ],
                "error": "Limited verifiable match information available for 2030-06-01.",
            }
        },
    }
    client = MatchDiscoveryClient(client=_FakeLLMClient({"soccer": response}))

    result = client.discover_matches(date_utc="2030-06-01", sports=["soccer"], limit_per_sport=5)

    soccer = result["results"]["soccer"]
    assert len(soccer["matches"]) == 1
    assert soccer["error"] == "Limited verifiable match information available for 2030-06-01."


class TestMatchesRequestedDateFilter:
    """Tests for _matches_requested_date timezone and edge-case handling."""

    def test_filter_rejects_match_when_kickoff_utc_is_previous_local_day(self):
        from match_discovery import _matches_requested_date

        match = {"home_team": "Arsenal", "away_team": "Chelsea", "kickoff_utc": "2026-06-05T23:00:00Z"}
        assert _matches_requested_date(match, "2026-06-06", timezone="America/Chicago") is False

    def test_filter_accepts_match_when_kickoff_utc_converts_to_requested_local_day(self):
        from match_discovery import _matches_requested_date

        match = {"home_team": "Arsenal", "away_team": "Chelsea", "kickoff_utc": "2026-06-07T03:00:00Z"}
        assert _matches_requested_date(match, "2026-06-06", timezone="America/Chicago") is True

    def test_filter_rejects_match_with_no_date_fields(self):
        from match_discovery import _matches_requested_date

        match = {"home_team": "Arsenal", "away_team": "Chelsea"}
        assert _matches_requested_date(match, "2026-06-06") is False

    def test_filter_still_works_without_timezone(self):
        from match_discovery import _matches_requested_date

        match = {"home_team": "Arsenal", "away_team": "Chelsea", "kickoff_utc": "2026-06-06T19:00:00Z"}
        assert _matches_requested_date(match, "2026-06-06") is True

    def test_filter_without_timezone_rejects_wrong_utc_date(self):
        from match_discovery import _matches_requested_date

        match = {"home_team": "Arsenal", "away_team": "Chelsea", "kickoff_utc": "2026-06-07T03:00:00Z"}
        assert _matches_requested_date(match, "2026-06-06") is False

    def test_event_date_takes_priority_over_kickoff_utc(self):
        from match_discovery import _matches_requested_date

        match = {
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "event_date": "2026-06-06",
            "kickoff_utc": "2026-06-07T03:00:00Z",
        }
        assert _matches_requested_date(match, "2026-06-06", timezone="America/Chicago") is True

    def test_event_date_mismatch_rejects(self):
        from match_discovery import _matches_requested_date

        match = {
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "event_date": "2026-06-05",
            "kickoff_utc": "2026-06-06T01:00:00Z",
        }
        assert _matches_requested_date(match, "2026-06-06") is False


class TestPastMatchFiltering:
    """Tests for _is_match_upcoming — filters out matches that already started."""

    def test_past_match_filtered_out(self):
        from datetime import datetime, timezone
        from match_discovery import _is_match_upcoming

        now = datetime(2026, 6, 7, 20, 0, 0, tzinfo=timezone.utc)
        match = {"home_team": "Arsenal", "away_team": "Chelsea", "kickoff_utc": "2026-06-07T18:00:00Z"}
        assert _is_match_upcoming(match, now=now) is False

    def test_future_match_kept(self):
        from datetime import datetime, timezone
        from match_discovery import _is_match_upcoming

        now = datetime(2026, 6, 7, 16, 0, 0, tzinfo=timezone.utc)
        match = {"home_team": "Arsenal", "away_team": "Chelsea", "kickoff_utc": "2026-06-07T18:00:00Z"}
        assert _is_match_upcoming(match, now=now) is True

    def test_match_within_buffer_kept(self):
        from datetime import datetime, timezone
        from match_discovery import _is_match_upcoming

        now = datetime(2026, 6, 7, 18, 5, 0, tzinfo=timezone.utc)
        match = {"home_team": "Arsenal", "away_team": "Chelsea", "kickoff_utc": "2026-06-07T18:00:00Z"}
        assert _is_match_upcoming(match, now=now, buffer_minutes=15) is True

    def test_match_past_buffer_filtered(self):
        from datetime import datetime, timezone
        from match_discovery import _is_match_upcoming

        now = datetime(2026, 6, 7, 18, 20, 0, tzinfo=timezone.utc)
        match = {"home_team": "Arsenal", "away_team": "Chelsea", "kickoff_utc": "2026-06-07T18:00:00Z"}
        assert _is_match_upcoming(match, now=now, buffer_minutes=15) is False

    def test_match_without_kickoff_utc_kept(self):
        from match_discovery import _is_match_upcoming

        match = {"home_team": "Arsenal", "away_team": "Chelsea", "event_date": "2026-06-07"}
        assert _is_match_upcoming(match) is True

    def test_invalid_kickoff_utc_kept(self):
        from match_discovery import _is_match_upcoming

        match = {"home_team": "Arsenal", "away_team": "Chelsea", "kickoff_utc": "not-a-date"}
        assert _is_match_upcoming(match) is True


class TestBasketballDiscoveryCriteria:
    """Basketball discovery should only include NBA, WNBA, and international cups."""

    def test_basketball_criteria_includes_nba_and_wnba(self) -> None:
        raw = build_match_discovery_user_prompt(
            date_utc="2026-06-08",
            sports=["basketball"],
            limit_per_sport=3,
        )
        parsed = json.loads(raw)
        criteria = parsed["selection_criteria_by_sport"]["basketball"]
        criteria_text = " ".join(criteria).lower()
        assert "nba" in criteria_text
        assert "wnba" in criteria_text

    def test_basketball_criteria_includes_international_cups(self) -> None:
        raw = build_match_discovery_user_prompt(
            date_utc="2026-06-08",
            sports=["basketball"],
            limit_per_sport=3,
        )
        parsed = json.loads(raw)
        criteria = parsed["selection_criteria_by_sport"]["basketball"]
        criteria_text = " ".join(criteria).lower()
        assert "olympic" in criteria_text or "fiba" in criteria_text

    def test_basketball_criteria_excludes_minor_leagues(self) -> None:
        raw = build_match_discovery_user_prompt(
            date_utc="2026-06-08",
            sports=["basketball"],
            limit_per_sport=3,
        )
        parsed = json.loads(raw)
        criteria = parsed["selection_criteria_by_sport"]["basketball"]
        first_criterion = criteria[0].lower()
        assert "euroleague" not in first_criterion
        assert "ncaab" not in first_criterion

    def test_basketball_criteria_has_exclusion_rule(self) -> None:
        raw = build_match_discovery_user_prompt(
            date_utc="2026-06-08",
            sports=["basketball"],
            limit_per_sport=3,
        )
        parsed = json.loads(raw)
        criteria = parsed["selection_criteria_by_sport"]["basketball"]
        criteria_text = " ".join(criteria).lower()
        assert "exclude" in criteria_text or "do not include" in criteria_text


class TestMatchDiscoveryClientConfig:
    """Tests for MatchDiscoveryClient.from_env configuration."""

    def test_gemini_client_uses_sufficient_max_output_tokens(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
        captured = {}

        import llm.gemini_client as gemini_mod
        original_init = gemini_mod.GeminiLLMClient.__init__

        def _capture_init(self, **kwargs):
            captured.update(kwargs)
            original_init(self, **kwargs)

        monkeypatch.setattr(gemini_mod.GeminiLLMClient, "__init__", _capture_init)

        from match_discovery import MatchDiscoveryClient
        MatchDiscoveryClient.from_env(provider="gemini")

        assert captured.get("max_output_tokens", 0) >= 4000
