"""Tests for GeminiChatClient used by LLMFixtureProvider."""

from __future__ import annotations

import pytest

from llm_fixture_provider import GeminiChatClient, LLMFixtureProviderError


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeGeminiSDK:
    def __init__(self, *, api_key: str):
        self.models = self
        self._api_key = api_key

    def generate_content(self, *, model, contents, config):
        return _FakeResponse('{"match_found": true, "competition": "Premier League"}')


def test_gemini_chat_client_returns_parsed_json() -> None:
    client = GeminiChatClient(api_key="test-key", model="gemini-2.5-flash", client_factory=_FakeGeminiSDK)

    result = client.generate_json(
        system_prompt="Resolve this fixture.",
        user_prompt='{"task": "resolve"}',
    )

    assert result["match_found"] is True
    assert result["competition"] == "Premier League"


def test_gemini_chat_client_raises_on_empty_response() -> None:
    class _EmptySDK:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponse("")

    client = GeminiChatClient(api_key="test-key", model="gemini-2.5-flash", client_factory=_EmptySDK)

    with pytest.raises(LLMFixtureProviderError, match="empty"):
        client.generate_json(system_prompt="x", user_prompt="y")


def test_gemini_chat_client_raises_on_sdk_error() -> None:
    class _FailingSDK:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            raise RuntimeError("network failure")

    client = GeminiChatClient(api_key="test-key", model="gemini-2.5-flash", client_factory=_FailingSDK)

    with pytest.raises(LLMFixtureProviderError, match="network failure"):
        client.generate_json(system_prompt="x", user_prompt="y")
