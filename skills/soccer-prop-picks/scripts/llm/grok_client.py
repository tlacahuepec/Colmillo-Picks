from __future__ import annotations

from time import sleep
from typing import Any, Callable
from urllib.request import urlopen

from llm.client import LLMClient, LLMError
from llm_fixture_provider import LLMFixtureProviderError, OpenAICompatibleChatClient


class GrokLLMClient(LLMClient):
    """xAI Grok adapter implementing the project LLM client contract via OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        retry_delay_seconds: float = 0.5,
        sleep_fn: Callable[[float], None] = sleep,
        urlopen_fn: Callable[..., Any] = urlopen,
    ) -> None:
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._sleep = sleep_fn
        self._inner = OpenAICompatibleChatClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=int(timeout_seconds),
            urlopen_fn=urlopen_fn,
        )

    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        attempts = self._max_retries + 1
        last_exc: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                result = self._inner.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
                if not isinstance(result, dict):
                    raise LLMError("Grok returned non-dict JSON output")
                return result
            except LLMFixtureProviderError as exc:
                last_exc = exc
                if attempt >= attempts:
                    raise LLMError(str(exc)) from exc
                self._sleep(self._retry_delay_seconds)
        raise LLMError(str(last_exc))
