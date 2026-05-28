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
        "date_utc": "2026-06-01",
        "generated_at_utc": "2026-06-01T12:00:00Z",
        "provider": "fake",
        "model": "fake-model",
        "sports": {
            sport: {
                "matches": [
                    {
                        "home_team": "Arsenal",
                        "away_team": "Liverpool",
                        "event_date": "2026-06-01",
                        "league": "premier_league",
                        "competition": "Premier League",
                        "kickoff_utc": "2026-06-01T19:00:00Z",
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
        date_utc="2026-06-01",
        sports=["soccer"],
        limit_per_sport=5,
    )

    match = result["results"]["soccer"]["matches"][0]
    assert match["home_team"] == "Arsenal"
    assert match["away_team"] == "Liverpool"
    assert match["event_date"] == "2026-06-01"
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
        date_utc="2026-06-01",
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
