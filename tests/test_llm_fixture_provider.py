from __future__ import annotations

import json

from tests.conftest import load_script_module


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.status = 200

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _config():
    provider_config = load_script_module("provider_config.py")
    return provider_config.LLMFixtureProviderConfig(
        provider="openai-compatible",
        api_key="fixture-key",
        base_url="https://llm.example.test/v1",
        model="fixture-model",
    )


def test_llm_fixture_provider_maps_chat_completion_json_to_fixture() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "match_found": True,
                                    "confidence": "high",
                                    "match_id": "llm-fixture-123",
                                    "competition": "Premier League",
                                    "competition_type": "league",
                                    "is_elimination": False,
                                    "overtime_possible": False,
                                    "kickoff_utc": "2026-05-03T15:30:00+00:00",
                                    "venue": {
                                        "name": "Emirates Stadium",
                                        "city": "London",
                                        "country": "England",
                                    },
                                    "teams": {
                                        "home": {"team_id": "ARS", "team_name": "Arsenal"},
                                        "away": {"team_id": "LIV", "team_name": "Liverpool"},
                                    },
                                    "status": {"long": "Not Started", "short": "NS"},
                                }
                            )
                        }
                    }
                ]
            }
        )

    provider = module.LLMFixtureProvider(config=_config(), urlopen_fn=fake_urlopen, timeout_seconds=7)

    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Arsenal",
            away_team="Liverpool",
            match_date="2026-05-03",
            competition="Premier League",
            league_id="39",
            season="2025",
        )
    )

    assert fixture == {
        "match_id": "llm-fixture-123",
        "competition": "Premier League",
        "competition_type": "league",
        "is_elimination": False,
        "overtime_possible": False,
        "kickoff_utc": "2026-05-03T15:30:00Z",
        "venue": {"name": "Emirates Stadium", "city": "London", "country": "England"},
        "teams": {
            "home": {"team_id": "ARS", "team_name": "Arsenal"},
            "away": {"team_id": "LIV", "team_name": "Liverpool"},
        },
        "status": {"long": "Not Started", "short": "NS"},
    }
    assert captured["url"] == "https://llm.example.test/v1/chat/completions"
    assert captured["timeout"] == 7
    body = captured["body"]
    assert body["model"] == "fixture-model"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["role"] == "system"


def test_llm_fixture_provider_returns_none_when_match_not_verified() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    class _Client:
        def generate_json(self, *, system_prompt, user_prompt):
            return {"match_found": False, "reason": "not verified"}

    provider = module.LLMFixtureProvider(config=_config(), client=_Client())

    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Arsenal",
            away_team="Liverpool",
            match_date="2026-05-03",
            competition="Premier League",
        )
    )

    assert fixture is None


def test_llm_fixture_provider_uses_safe_defaults_for_partial_fixture_json() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    class _Client:
        def generate_json(self, *, system_prompt, user_prompt):
            return {
                "match_found": True,
                "competition": "Premier League",
                "teams": {
                    "home": {"team_name": "Arsenal"},
                    "away": {"team_name": "Liverpool"},
                },
                "venue": {},
            }

    provider = module.LLMFixtureProvider(config=_config(), client=_Client())

    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Arsenal",
            away_team="Liverpool",
            match_date="2026-05-03",
            competition="Premier League",
        )
    )

    assert fixture is not None
    assert fixture["match_id"] == "llm-premier-league-arsenal-liverpool-2026-05-03"
    assert fixture["teams"]["home"]["team_id"] == "ARS"
    assert fixture["teams"]["away"]["team_id"] == "LIV"
    assert fixture["venue"] == {"name": "Unknown Venue", "city": "Unknown", "country": "Unknown"}
