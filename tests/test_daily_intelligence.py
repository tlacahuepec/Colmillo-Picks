"""Tests for DailyIntelligenceClient (provider-agnostic)."""

from __future__ import annotations

import pytest

from tests.conftest import load_script_module


def _load():
    return load_script_module("daily_intelligence.py")


def _minimal_briefing(date_utc: str = "2026-05-21") -> dict:
    return {
        "schema_version": "v1.0.0",
        "date_utc": date_utc,
        "generated_at_utc": "2026-05-21T10:00:00Z",
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "top_matches": [
            {
                "rank": 1,
                "match_importance": "high",
                "competition": "Champions League",
                "kickoff_utc": "2026-05-21T19:00:00Z",
                "venue": {"name": "Camp Nou", "city": "Barcelona", "country": "Spain"},
                "teams": {
                    "home": {"name": "Barcelona", "team_id": "BAR"},
                    "away": {"name": "Real Madrid", "team_id": "RMA"},
                },
                "injuries": [],
                "projected_lineups": {
                    "home": {"formation": "4-3-3", "starters": [], "status": "projected"},
                    "away": {"formation": "4-3-3", "starters": [], "status": "projected"},
                },
                "odds": {"home_win": 2.10, "draw": 3.40, "away_win": 3.50, "source": None, "captured_at_utc": None},
                "notes": None,
            }
        ],
    }


class _FakeLLMClient:
    """Mock implementing LLMClient protocol."""

    def __init__(self, response: dict) -> None:
        self._response = response
        self.calls: list[dict] = []

    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, "schema": schema})
        return self._response


class _FailingLLMClient:
    """Mock that raises LLMError."""

    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        from llm.client import LLMError

        raise LLMError("provider timeout")


def test_from_env_defaults_to_gemini_when_no_provider_set() -> None:
    module = _load()
    with pytest.raises(module.DailyIntelligenceError, match="GEMINI_API_KEY"):
        module.DailyIntelligenceClient.from_env(getenv=lambda _: None)


def test_from_env_raises_when_gemini_key_missing() -> None:
    module = _load()
    with pytest.raises(module.DailyIntelligenceError, match="GEMINI_API_KEY"):
        module.DailyIntelligenceClient.from_env(getenv=lambda _: None)


def test_from_env_raises_when_grok_key_missing() -> None:
    module = _load()
    with pytest.raises(module.DailyIntelligenceError, match="XAI_API_KEY"):
        module.DailyIntelligenceClient.from_env(getenv=lambda _: None, provider="grok")


def test_from_env_raises_when_openai_key_missing() -> None:
    module = _load()
    with pytest.raises(module.DailyIntelligenceError, match="OPENAI_API_KEY"):
        module.DailyIntelligenceClient.from_env(getenv=lambda _: None, provider="openai")


def test_from_env_raises_on_unsupported_provider() -> None:
    module = _load()
    with pytest.raises(module.DailyIntelligenceError, match="Unsupported"):
        module.DailyIntelligenceClient.from_env(getenv=lambda _: None, provider="anthropic")


def test_fetch_daily_briefing_returns_dict_with_top_matches() -> None:
    module = _load()
    briefing = _minimal_briefing()
    fake_client = _FakeLLMClient(briefing)

    client = module.DailyIntelligenceClient(client=fake_client)
    result = client.fetch_daily_briefing(date_utc="2026-05-21", top_n=1)

    assert isinstance(result["top_matches"], list)
    assert result["date_utc"] == "2026-05-21"
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["schema"] == {}


def test_fetch_daily_briefing_raises_on_llm_error() -> None:
    module = _load()
    failing_client = _FailingLLMClient()

    client = module.DailyIntelligenceClient(client=failing_client)

    with pytest.raises(module.DailyIntelligenceError, match="provider timeout"):
        client.fetch_daily_briefing(date_utc="2026-05-21")


def test_fetch_daily_briefing_raises_when_top_matches_missing() -> None:
    module = _load()
    fake_client = _FakeLLMClient({"schema_version": "v1.0.0"})

    client = module.DailyIntelligenceClient(client=fake_client)

    with pytest.raises(module.DailyIntelligenceError, match="top_matches"):
        client.fetch_daily_briefing(date_utc="2026-05-21")


def test_backward_compat_shim_exports_aliases() -> None:
    module = load_script_module("grok_daily_intelligence.py")
    assert module.GrokDailyIntelligenceClient.__name__ == "DailyIntelligenceClient"
    assert module.GrokDailyIntelligenceError.__name__ == "DailyIntelligenceError"
