from __future__ import annotations

from diagnostics_support import diagnostic_stage, provider_attempt, retry_sleep

from time import sleep
from typing import Any, Callable

from llm.client import LLMClient, LLMError


class OpenAILLMClient(LLMClient):
    """OpenAI-backed adapter implementing the project LLM client contract."""

    def __init__(
        self,
        *,
        sdk_client: Any,
        model: str,
        timeout_seconds: float = 20.0,
        max_retries: int = 1,
        retry_delay_seconds: float = 0.5,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        self._sdk_client = sdk_client
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._sleep = retry_sleep(sleep_fn, provider="openai", model=model)

    @diagnostic_stage("llm_generate", provider="openai")
    def generate_structured(
        self, *, system_prompt: str, user_prompt: str, schema: dict, temperature: float | None = None
    ) -> dict:
        attempts = self._max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                with provider_attempt("openai", attempt=attempt, model=self._model, timeout_seconds=self._timeout_seconds) as info:
                    response = self._sdk_client.responses.parse(
                        model=self._model,
                        input=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        text={"format": {"type": "json_schema", "name": "response", "schema": schema}},
                        timeout=self._timeout_seconds,
                    )
                    parsed = getattr(response, "output_parsed", None)
                    usage = getattr(response, "usage", None)
                    if usage:
                        info.update(prompt_tokens=getattr(usage, "input_tokens", None),
                                    completion_tokens=getattr(usage, "output_tokens", None),
                                    total_tokens=getattr(usage, "total_tokens", None))
                    if not isinstance(parsed, dict):
                        raise LLMError("Provider returned non-dict structured output")
                    return parsed
            except TimeoutError as exc:
                if attempt >= attempts:
                    raise LLMError(str(exc)) from exc
                self._sleep(self._retry_delay_seconds)
            except LLMError:
                raise
            except Exception as exc:  # provider-specific exceptions
                raise LLMError(str(exc)) from exc

        raise LLMError("Provider failed without returning data")
