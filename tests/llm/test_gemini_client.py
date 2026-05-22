"""Tests for the Gemini LLM client and provider wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from llm.client import LLMError
from llm.gemini_client import GeminiLLMClient
from llm.provider_adapter import build_enrich_with_llm, validate_llm_runtime_config


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeClient:
    def __init__(self, *, api_key: str):
        self.api_key = api_key
        self.models = self

    def generate_content(self, *, model, contents, config):
        return _FakeResponse('{"scores": [{"player": "A", "confidence": "high"}]}')


class _FailingClient:
    def __init__(self, *, api_key: str):
        self.models = self

    def generate_content(self, **kwargs):
        raise TimeoutError("request timed out")


def test_gemini_client_returns_parsed_json() -> None:
    client = GeminiLLMClient(api_key="test-key", client_factory=_FakeClient)

    result = client.generate_structured(
        system_prompt="You are a sports analyst.",
        user_prompt="Score these picks.",
        schema={},
    )

    assert result == {"scores": [{"player": "A", "confidence": "high"}]}


def test_gemini_client_raises_on_empty_response() -> None:
    class _EmptyClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponse("")

    client = GeminiLLMClient(api_key="test-key", client_factory=_EmptyClient)

    with pytest.raises(LLMError, match="empty response"):
        client.generate_structured(system_prompt="x", user_prompt="y", schema={})


def test_gemini_client_raises_on_whitespace_only_response() -> None:
    class _WhitespaceClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponse("\n  \n")

    client = GeminiLLMClient(api_key="test-key", client_factory=_WhitespaceClient)

    with pytest.raises(LLMError, match="empty response"):
        client.generate_structured(system_prompt="x", user_prompt="y", schema={})


def test_gemini_client_raises_on_invalid_json() -> None:
    class _BadJsonClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponse("not json at all")

    client = GeminiLLMClient(api_key="test-key", client_factory=_BadJsonClient)

    with pytest.raises(LLMError, match="invalid JSON"):
        client.generate_structured(system_prompt="x", user_prompt="y", schema={})


def test_gemini_client_retries_on_timeout() -> None:
    call_count = 0

    class _TimeoutThenSuccessClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("timed out")
            return _FakeResponse('{"ok": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_TimeoutThenSuccessClient,
        max_retries=1,
        sleep_fn=lambda _: None,
    )

    result = client.generate_structured(system_prompt="x", user_prompt="y", schema={})
    assert result == {"ok": True}
    assert call_count == 2


def test_validate_accepts_gemini_provider() -> None:
    validate_llm_runtime_config(
        use_llm=True,
        llm_provider="gemini",
        getenv=lambda k: "fake-key" if k == "GEMINI_API_KEY" else None,
    )


def test_validate_rejects_gemini_without_key() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        validate_llm_runtime_config(
            use_llm=True,
            llm_provider="gemini",
            getenv=lambda _: None,
        )


def test_build_enrich_with_llm_gemini_provider() -> None:
    enrich_fn = build_enrich_with_llm(
        use_llm=True,
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        getenv=lambda k: "fake-key" if k == "GEMINI_API_KEY" else None,
        openai_client_factory=lambda **_: MagicMock(),
    )

    assert callable(enrich_fn)


def test_validate_falls_back_to_env_var_when_no_flag() -> None:
    env = {"COLMILLO_LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "fake-key"}
    validate_llm_runtime_config(
        use_llm=True,
        llm_provider=None,
        getenv=env.get,
    )


def test_validate_error_mentions_env_var_when_neither_set() -> None:
    with pytest.raises(ValueError, match="COLMILLO_LLM_PROVIDER"):
        validate_llm_runtime_config(
            use_llm=True,
            llm_provider=None,
            getenv=lambda _: None,
        )


def test_explicit_flag_overrides_env_var() -> None:
    env = {"COLMILLO_LLM_PROVIDER": "openai", "GEMINI_API_KEY": "fake-key"}
    validate_llm_runtime_config(
        use_llm=True,
        llm_provider="gemini",
        getenv=env.get,
    )


def test_build_enrich_uses_env_provider_when_flag_is_none() -> None:
    env = {"COLMILLO_LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "fake-key"}
    enrich_fn = build_enrich_with_llm(
        use_llm=True,
        llm_provider=None,
        llm_model=None,
        getenv=env.get,
    )

    assert callable(enrich_fn)


def test_gemini_client_passes_google_search_tool_when_grounding_enabled() -> None:
    captured_config = {}

    class _CapturingClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, *, model, contents, config):
            captured_config.update(config)
            return _FakeResponse('{"match_found": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_CapturingClient,
        search_grounding=True,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert "tools" in captured_config
    assert captured_config["tools"] == [{"google_search": {}}]
    assert "response_mime_type" not in captured_config


def test_gemini_client_omits_tools_when_grounding_disabled() -> None:
    captured_config = {}

    class _CapturingClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, *, model, contents, config):
            captured_config.update(config)
            return _FakeResponse('{"match_found": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_CapturingClient,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert "tools" not in captured_config
    assert captured_config["response_mime_type"] == "application/json"


def test_gemini_client_strips_markdown_fences_from_response() -> None:
    class _MarkdownClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, *, model, contents, config):
            return _FakeResponse('```json\n{"competition": "DFB Pokal", "match_found": true}\n```')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_MarkdownClient,
        search_grounding=True,
    )
    result = client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert result == {"competition": "DFB Pokal", "match_found": True}


def test_gemini_client_parses_first_json_object_when_extra_data_follows() -> None:
    class _ExtraDataClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, *, model, contents, config):
            return _FakeResponse('{"teams": {"home": "Bayern"}}\n{"extra": "data"}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_ExtraDataClient,
        search_grounding=True,
    )
    result = client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert result == {"teams": {"home": "Bayern"}}


def test_gemini_client_retries_on_rate_limit_429() -> None:
    call_count = 0

    class _RateLimitClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 RESOURCE_EXHAUSTED: quota exceeded")
            return _FakeResponse('{"ok": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_RateLimitClient,
        max_retries=2,
        retry_delay_seconds=0.01,
        sleep_fn=lambda _: None,
    )

    result = client.generate_structured(system_prompt="x", user_prompt="y", schema={})
    assert result == {"ok": True}
    assert call_count == 2


def test_gemini_client_raises_after_exhausting_rate_limit_retries() -> None:
    class _AlwaysRateLimitClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            raise Exception("429 RESOURCE_EXHAUSTED: quota exceeded")

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_AlwaysRateLimitClient,
        max_retries=1,
        retry_delay_seconds=0.01,
        sleep_fn=lambda _: None,
    )

    with pytest.raises(LLMError, match="429"):
        client.generate_structured(system_prompt="x", user_prompt="y", schema={})
