"""Tests for GrokDailyIntelligenceClient."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError

import pytest

from tests.conftest import load_script_module


def _load():
    return load_script_module("grok_daily_intelligence.py")


def _chat_response(payload: dict) -> bytes:
    return json.dumps(
        {"choices": [{"message": {"content": json.dumps(payload)}}]}
    ).encode("utf-8")


class _FakeHTTPResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.status = 200

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _minimal_briefing(date_utc: str = "2026-05-21") -> dict:
    return {
        "schema_version": "v1.0.0",
        "date_utc": date_utc,
        "generated_at_utc": "2026-05-21T10:00:00Z",
        "provider": "xai",
        "model": "grok-3",
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


def test_from_env_raises_when_api_key_missing() -> None:
    module = _load()
    with pytest.raises(module.GrokDailyIntelligenceError, match="XAI_API_KEY"):
        module.GrokDailyIntelligenceClient.from_env(getenv=lambda _: None)


def test_from_env_reads_defaults_when_optional_vars_absent() -> None:
    module = _load()
    client = module.GrokDailyIntelligenceClient.from_env(
        getenv=lambda k: "sk-x" if k == "XAI_API_KEY" else None
    )
    assert client.base_url == "https://api.x.ai/v1"
    assert client.model == "grok-3"


def test_from_env_reads_custom_base_url_and_model() -> None:
    module = _load()
    env = {"XAI_API_KEY": "sk-x", "XAI_BASE_URL": "https://custom.ai/v1", "XAI_MODEL": "grok-3-mini"}
    client = module.GrokDailyIntelligenceClient.from_env(getenv=env.get)
    assert client.base_url == "https://custom.ai/v1"
    assert client.model == "grok-3-mini"


def test_fetch_daily_briefing_returns_dict_with_top_matches() -> None:
    module = _load()
    briefing = _minimal_briefing()

    def fake_urlopen(request, timeout=0):
        return _FakeHTTPResponse(_chat_response(briefing))

    client = module.GrokDailyIntelligenceClient(
        api_key="sk-x",
        base_url="https://api.x.ai/v1",
        model="grok-3",
        urlopen_fn=fake_urlopen,
    )

    result = client.fetch_daily_briefing(date_utc="2026-05-21", top_n=1)
    assert isinstance(result["top_matches"], list)
    assert result["date_utc"] == "2026-05-21"


def test_fetch_daily_briefing_raises_on_http_error() -> None:
    module = _load()

    def fake_urlopen(request, timeout=0):
        raise HTTPError(url="", code=500, msg="Server Error", hdrs=None, fp=None)

    client = module.GrokDailyIntelligenceClient(
        api_key="sk-x",
        base_url="https://api.x.ai/v1",
        model="grok-3",
        urlopen_fn=fake_urlopen,
    )

    with pytest.raises(module.GrokDailyIntelligenceError, match="500"):
        client.fetch_daily_briefing(date_utc="2026-05-21")


def test_fetch_daily_briefing_raises_when_top_matches_missing() -> None:
    module = _load()

    def fake_urlopen(request, timeout=0):
        return _FakeHTTPResponse(_chat_response({"schema_version": "v1.0.0"}))

    client = module.GrokDailyIntelligenceClient(
        api_key="sk-x",
        base_url="https://api.x.ai/v1",
        model="grok-3",
        urlopen_fn=fake_urlopen,
    )

    with pytest.raises(module.GrokDailyIntelligenceError, match="top_matches"):
        client.fetch_daily_briefing(date_utc="2026-05-21")


def test_fetch_daily_briefing_raises_on_url_error() -> None:
    module = _load()

    def fake_urlopen(request, timeout=0):
        raise URLError("network unreachable")

    client = module.GrokDailyIntelligenceClient(
        api_key="sk-x",
        base_url="https://api.x.ai/v1",
        model="grok-3",
        urlopen_fn=fake_urlopen,
    )

    with pytest.raises(module.GrokDailyIntelligenceError):
        client.fetch_daily_briefing(date_utc="2026-05-21")
