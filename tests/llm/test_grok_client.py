"""Tests for GrokLLMClient and provider_adapter Grok wiring."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

import pytest

from llm.client import LLMError
from llm.grok_client import GrokLLMClient
from llm.provider_adapter import build_enrich_with_llm, validate_llm_runtime_config


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


def _make_client(urlopen_fn, *, model: str = "grok-3", max_retries: int = 1) -> GrokLLMClient:
    return GrokLLMClient(
        api_key="sk-test",
        base_url="https://api.x.ai/v1",
        model=model,
        max_retries=max_retries,
        sleep_fn=lambda _: None,
        urlopen_fn=urlopen_fn,
    )


def test_grok_client_delegates_generate_structured_to_openai_compatible_chat() -> None:
    expected = {"scores": [{"player": "A", "confidence": "high"}]}
    captured: dict = {}

    def fake_urlopen(request, timeout=0):
        captured["auth"] = request.get_header("Authorization")
        return _FakeHTTPResponse(_chat_response(expected))

    client = _make_client(fake_urlopen)
    result = client.generate_structured(system_prompt="sys", user_prompt="usr", schema={})

    assert result == expected
    assert captured["auth"] == "Bearer sk-test"


def test_grok_client_maps_http_error_to_llm_error() -> None:
    def fake_urlopen(request, timeout=0):
        raise HTTPError(url="", code=404, msg="Not Found", hdrs=None, fp=None)

    client = _make_client(fake_urlopen)

    with pytest.raises(LLMError, match="404"):
        client.generate_structured(system_prompt="sys", user_prompt="usr", schema={})


def test_grok_client_maps_url_error_to_llm_error() -> None:
    def fake_urlopen(request, timeout=0):
        raise URLError("connection refused")

    client = _make_client(fake_urlopen, max_retries=0)

    with pytest.raises(LLMError):
        client.generate_structured(system_prompt="sys", user_prompt="usr", schema={})


def test_grok_client_retries_on_url_error_then_succeeds() -> None:
    call_count = 0
    expected = {"ok": True}

    def fake_urlopen(request, timeout=0):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise URLError("temporary failure")
        return _FakeHTTPResponse(_chat_response(expected))

    slept: list[float] = []
    client = GrokLLMClient(
        api_key="sk-test",
        base_url="https://api.x.ai/v1",
        model="grok-3",
        max_retries=1,
        sleep_fn=slept.append,
        urlopen_fn=fake_urlopen,
    )

    result = client.generate_structured(system_prompt="sys", user_prompt="usr", schema={})
    assert result == expected
    assert call_count == 2
    assert len(slept) == 1


def test_grok_client_raises_llm_error_when_all_retries_exhausted() -> None:
    def fake_urlopen(request, timeout=0):
        raise URLError("always fails")

    client = GrokLLMClient(
        api_key="sk-test",
        base_url="https://api.x.ai/v1",
        model="grok-3",
        max_retries=1,
        sleep_fn=lambda _: None,
        urlopen_fn=fake_urlopen,
    )

    with pytest.raises(LLMError):
        client.generate_structured(system_prompt="sys", user_prompt="usr", schema={})


# --- provider_adapter integration ---


def test_validate_accepts_grok_with_xai_key() -> None:
    validate_llm_runtime_config(
        use_llm=True,
        llm_provider="grok",
        getenv=lambda k: "sk-x" if k == "XAI_API_KEY" else None,
    )


def test_validate_rejects_grok_without_xai_key() -> None:
    with pytest.raises(ValueError, match="XAI_API_KEY"):
        validate_llm_runtime_config(
            use_llm=True,
            llm_provider="grok",
            getenv=lambda _: None,
        )


def test_validate_still_rejects_unknown_provider_after_grok_added() -> None:
    with pytest.raises(ValueError, match="openai, gemini, grok"):
        validate_llm_runtime_config(
            use_llm=True,
            llm_provider="anthropic",
            getenv=lambda _: "fake-key",
        )


def test_build_enrich_with_llm_grok_returns_callable() -> None:
    def fake_urlopen(request, timeout=0):
        return _FakeHTTPResponse(_chat_response({"ok": True}))

    enrich_fn = build_enrich_with_llm(
        use_llm=True,
        llm_provider="grok",
        llm_model="grok-3",
        getenv=lambda k: {
            "XAI_API_KEY": "sk-x",
            "XAI_BASE_URL": "https://api.x.ai/v1",
        }.get(k),
        openai_client_factory=lambda **_: MagicMock(),
    )

    assert callable(enrich_fn)


def test_build_enrich_with_llm_grok_uses_env_model_when_flag_is_none() -> None:
    enrich_fn = build_enrich_with_llm(
        use_llm=True,
        llm_provider="grok",
        llm_model=None,
        getenv=lambda k: {
            "XAI_API_KEY": "sk-x",
            "XAI_BASE_URL": "https://api.x.ai/v1",
            "XAI_MODEL": "grok-3-mini",
        }.get(k),
        openai_client_factory=lambda **_: MagicMock(),
    )

    assert callable(enrich_fn)
