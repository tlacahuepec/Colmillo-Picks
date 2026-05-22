"""Backward-compat tests for grok_daily_intelligence shim.

These verify the shim module re-exports work and the from_env path for grok provider.
"""

from __future__ import annotations

import pytest

from tests.conftest import load_script_module


def _load():
    return load_script_module("grok_daily_intelligence.py")


def test_shim_exports_grok_daily_intelligence_client() -> None:
    module = _load()
    assert hasattr(module, "GrokDailyIntelligenceClient")
    assert hasattr(module, "GrokDailyIntelligenceError")


def test_from_env_raises_when_no_key_available() -> None:
    module = _load()
    with pytest.raises(module.GrokDailyIntelligenceError, match="GEMINI_API_KEY"):
        module.GrokDailyIntelligenceClient.from_env(getenv=lambda _: None)


def test_from_env_with_grok_provider_raises_when_xai_key_missing() -> None:
    module = _load()
    with pytest.raises(module.GrokDailyIntelligenceError, match="XAI_API_KEY"):
        module.GrokDailyIntelligenceClient.from_env(getenv=lambda _: None, provider="grok")


def test_fetch_daily_briefing_via_shim() -> None:
    module = _load()

    class _FakeClient:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {
                "schema_version": "v1.0.0",
                "date_utc": "2026-05-21",
                "generated_at_utc": "2026-05-21T10:00:00Z",
                "top_matches": [{"rank": 1}],
            }

    client = module.GrokDailyIntelligenceClient(client=_FakeClient())
    result = client.fetch_daily_briefing(date_utc="2026-05-21", top_n=1)
    assert "top_matches" in result
