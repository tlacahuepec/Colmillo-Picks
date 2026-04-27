from __future__ import annotations

import pytest

from llm.client import LLMError
from llm.mock_client import DeterministicMockLLMClient
from llm.openai_client import OpenAILLMClient


class _FakeResponse:
    def __init__(self, parsed: dict[str, object]) -> None:
        self.output_parsed = parsed


class _FakeResponsesAPI:
    def __init__(self, outcomes: list[object]) -> None:
        self._outcomes = outcomes
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _FakeSDKClient:
    def __init__(self, outcomes: list[object]) -> None:
        self.responses = _FakeResponsesAPI(outcomes)


def test_openai_adapter_returns_parsed_dict_shape() -> None:
    sdk_client = _FakeSDKClient([_FakeResponse({"pick": "over", "confidence": 0.61})])
    adapter = OpenAILLMClient(sdk_client=sdk_client, model="gpt-test", timeout_seconds=3.5)

    result = adapter.generate_structured(
        system_prompt="system",
        user_prompt="user",
        schema={"type": "object"},
    )

    assert result == {"pick": "over", "confidence": 0.61}
    assert sdk_client.responses.calls[0]["model"] == "gpt-test"


def test_openai_adapter_maps_provider_errors_to_llm_error() -> None:
    sdk_client = _FakeSDKClient([RuntimeError("provider exploded")])
    adapter = OpenAILLMClient(sdk_client=sdk_client, model="gpt-test")

    with pytest.raises(LLMError, match="provider exploded"):
        adapter.generate_structured(system_prompt="system", user_prompt="user", schema={"type": "object"})


def test_openai_adapter_retries_timeouts_then_succeeds() -> None:
    sdk_client = _FakeSDKClient(
        [
            TimeoutError("timed out-1"),
            TimeoutError("timed out-2"),
            _FakeResponse({"ok": True}),
        ]
    )
    sleeps: list[float] = []
    adapter = OpenAILLMClient(
        sdk_client=sdk_client,
        model="gpt-test",
        max_retries=2,
        retry_delay_seconds=0.25,
        sleep_fn=sleeps.append,
    )

    result = adapter.generate_structured(system_prompt="system", user_prompt="user", schema={"type": "object"})

    assert result == {"ok": True}
    assert len(sdk_client.responses.calls) == 3
    assert sleeps == [0.25, 0.25]


def test_mock_client_returns_deterministic_copy() -> None:
    fixture = {"pick": "under", "confidence": 0.44, "reasons": ["fixture"]}
    client = DeterministicMockLLMClient(fixture=fixture)

    result = client.generate_structured(system_prompt="a", user_prompt="b", schema={"type": "object"})
    result["reasons"].append("mutated")

    second = client.generate_structured(system_prompt="a", user_prompt="b", schema={"type": "object"})
    assert second == fixture
