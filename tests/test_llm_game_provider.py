"""Tests for basketball LLM game context provider."""

from __future__ import annotations

import json

from tests.conftest import load_script_module


def _game_config():
    provider_config = load_script_module("provider_config.py")
    return provider_config.LLMFixtureProviderConfig(
        provider="openai-compatible",
        api_key="game-key",
        base_url="https://llm.example.test/v1",
        model="game-model",
    )


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


def _full_game_response() -> dict:
    return {
        "game_found": True,
        "confidence": "high",
        "home_team": "Lakers",
        "away_team": "Celtics",
        "tipoff_utc": "2026-06-01T19:30:00Z",
        "home_pace": 100.2,
        "away_pace": 98.5,
        "projected_game_pace": 99.3,
        "home_defensive_rating": 112.3,
        "away_defensive_rating": 108.7,
        "home_win_prob": 0.55,
        "away_win_prob": 0.45,
        "over_under_total": 224.5,
        "spread": -3.5,
        "home_rest_days": 2,
        "away_rest_days": 1,
        "venue": "Crypto.com Arena",
        "is_playoff": False,
    }


class TestLLMGameProviderHappyPath:
    def test_maps_llm_response_to_game_context(self) -> None:
        module = load_script_module("llm_game_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return _full_game_response()

        provider = module.LLMGameProvider(config=_game_config(), client=_Client())
        result = provider.lookup_game(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        assert result is not None
        assert result["home_team"] == "Lakers"
        assert result["away_team"] == "Celtics"
        assert result["tipoff_utc"] == "2026-06-01T19:30:00Z"
        assert result["home_pace"] == 100.2
        assert result["away_pace"] == 98.5
        assert result["projected_game_pace"] == 99.3
        assert result["home_defensive_rating"] == 112.3
        assert result["away_defensive_rating"] == 108.7
        assert result["home_win_prob"] == 0.55
        assert result["away_win_prob"] == 0.45
        assert result["over_under_total"] == 224.5
        assert result["spread"] == -3.5
        assert result["home_rest_days"] == 2
        assert result["away_rest_days"] == 1
        assert result["venue"] == "Crypto.com Arena"

    def test_uses_urlopen_to_call_chat_completions(self) -> None:
        module = load_script_module("llm_game_provider.py")
        captured: dict = {}

        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return _FakeResponse(
                {"choices": [{"message": {"content": json.dumps(_full_game_response())}}]}
            )

        provider = module.LLMGameProvider(
            config=_game_config(), urlopen_fn=fake_urlopen, timeout_seconds=10,
        )
        provider.lookup_game(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        assert captured["url"] == "https://llm.example.test/v1/chat/completions"
        assert captured["timeout"] == 10
        body = captured["body"]
        assert body["model"] == "game-model"
        assert body["response_format"] == {"type": "json_object"}
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"


class TestLLMGameProviderNotFound:
    def test_returns_none_when_game_not_found(self) -> None:
        module = load_script_module("llm_game_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return {"game_found": False, "reason": "No game scheduled"}

        provider = module.LLMGameProvider(config=_game_config(), client=_Client())
        result = provider.lookup_game(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        assert result is None

    def test_soft_accepts_high_confidence_match(self) -> None:
        module = load_script_module("llm_game_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                resp = _full_game_response()
                resp["game_found"] = False
                resp["confidence"] = "high"
                return resp

        provider = module.LLMGameProvider(config=_game_config(), client=_Client())
        result = provider.lookup_game(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        assert result is not None
        assert result["home_team"] == "Lakers"

    def test_does_not_soft_accept_low_confidence(self) -> None:
        module = load_script_module("llm_game_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                resp = _full_game_response()
                resp["game_found"] = False
                resp["confidence"] = "low"
                return resp

        provider = module.LLMGameProvider(config=_game_config(), client=_Client())
        result = provider.lookup_game(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        assert result is None


class TestLLMGameProviderFallback:
    def test_returns_neutral_defaults_on_partial_response(self) -> None:
        module = load_script_module("llm_game_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return {
                    "game_found": True,
                    "confidence": "medium",
                    "home_team": "Lakers",
                    "away_team": "Celtics",
                }

        provider = module.LLMGameProvider(config=_game_config(), client=_Client())
        result = provider.lookup_game(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        assert result is not None
        assert result["home_pace"] is None
        assert result["away_pace"] is None
        assert result["home_defensive_rating"] is None
        assert result["over_under_total"] is None
        assert result["spread"] is None
        assert result["home_rest_days"] is None
        assert result["venue"] is None

    def test_returns_neutral_defaults_on_llm_error(self) -> None:
        module = load_script_module("llm_game_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                raise module.LLMGameProviderError("timeout")

        provider = module.LLMGameProvider(config=_game_config(), client=_Client())
        result = provider.lookup_game(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        assert result is not None
        assert result["home_team"] == "Lakers"
        assert result["away_team"] == "Celtics"
        assert result["home_pace"] is None
        assert result["spread"] is None


class TestLLMGameProviderPrompt:
    def test_system_prompt_mentions_basketball(self) -> None:
        module = load_script_module("llm_game_provider.py")
        prompt = module.LLMGameProvider._build_system_prompt()
        assert "basketball" in prompt.lower() or "nba" in prompt.lower()

    def test_user_prompt_includes_teams_and_date(self) -> None:
        module = load_script_module("llm_game_provider.py")
        prompt = module.LLMGameProvider._build_user_prompt(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        prompt_data = json.loads(prompt)
        assert prompt_data["request"]["home_team"] == "Lakers"
        assert prompt_data["request"]["away_team"] == "Celtics"
        assert prompt_data["request"]["match_date"] == "2026-06-01"

    def test_user_prompt_specifies_required_json_shape(self) -> None:
        module = load_script_module("llm_game_provider.py")
        prompt = module.LLMGameProvider._build_user_prompt(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        prompt_data = json.loads(prompt)
        shape = prompt_data["required_json_shape"]
        assert "home_pace" in shape
        assert "away_pace" in shape
        assert "home_defensive_rating" in shape
        assert "over_under_total" in shape
        assert "spread" in shape
        assert "home_rest_days" in shape
        assert "away_rest_days" in shape
        assert "venue" in shape

    def test_user_prompt_includes_rules(self) -> None:
        module = load_script_module("llm_game_provider.py")
        prompt = module.LLMGameProvider._build_user_prompt(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        prompt_data = json.loads(prompt)
        assert "rules" in prompt_data
        assert len(prompt_data["rules"]) > 0


class TestLLMGameProviderDebug:
    def test_debug_logs_request_and_response(self, monkeypatch, capsys) -> None:
        module = load_script_module("llm_game_provider.py")
        monkeypatch.setenv("COLMILLO_GAME_LLM_DEBUG", "1")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return _full_game_response()

        provider = module.LLMGameProvider(config=_game_config(), client=_Client())
        provider.lookup_game(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        stderr = capsys.readouterr().err
        assert "[game-llm-debug] request:" in stderr
        assert "[game-llm-debug] response:" in stderr

    def test_debug_logs_when_game_not_found(self, monkeypatch, capsys) -> None:
        module = load_script_module("llm_game_provider.py")
        monkeypatch.setenv("COLMILLO_GAME_LLM_DEBUG", "1")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return {"game_found": False, "reason": "Teams not scheduled"}

        provider = module.LLMGameProvider(config=_game_config(), client=_Client())
        provider.lookup_game(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        stderr = capsys.readouterr().err
        assert "[game-llm-debug] game_not_found:" in stderr
        assert "Teams not scheduled" in stderr


class TestLLMGameProviderSources:
    def test_captures_last_sources_from_client(self) -> None:
        module = load_script_module("llm_game_provider.py")

        class _FakeSource:
            def __init__(self, url, title):
                self.url = url
                self.title = title

        class _ClientWithSources:
            def __init__(self):
                self.last_sources = [
                    _FakeSource("https://nba.example.com", "NBA Stats"),
                ]

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return _full_game_response()

        provider = module.LLMGameProvider(config=_game_config(), client=_ClientWithSources())
        provider.lookup_game(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        assert len(provider.last_sources) == 1
        assert provider.last_sources[0].url == "https://nba.example.com"
