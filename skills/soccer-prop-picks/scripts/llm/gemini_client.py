from __future__ import annotations

import json
from time import sleep
from typing import Any, Callable

from llm.client import LLMClient, LLMError

_DEFAULT_MODEL = "gemini-2.5-flash"


class GeminiLLMClient(LLMClient):
    """Google Gemini adapter implementing the project LLM client contract."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        max_output_tokens: int = 2000,
        timeout_seconds: float = 20.0,
        max_retries: int = 1,
        retry_delay_seconds: float = 0.5,
        search_grounding: bool = False,
        sleep_fn: Callable[[float], None] = sleep,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._search_grounding = search_grounding
        self._sleep = sleep_fn

        if client_factory is not None:
            self._client = client_factory(api_key=api_key)
        else:
            from google import genai

            self._client = genai.Client(api_key=api_key)

    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        prompt = f"{system_prompt}\n\n{user_prompt}\n\nRespond with valid JSON only."
        attempts = self._max_retries + 1

        for attempt in range(1, attempts + 1):
            try:
                config: dict[str, Any] = {
                    "max_output_tokens": self._max_output_tokens,
                    "thinking_config": {"thinking_budget": 0},
                }
                if self._search_grounding:
                    config["tools"] = [{"google_search": {}}]
                else:
                    config["response_mime_type"] = "application/json"
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=config,
                )
                text = response.text
                if not text:
                    raise LLMError("Gemini returned empty response")
                parsed = json.loads(text)
                if not isinstance(parsed, dict):
                    raise LLMError("Gemini returned non-dict JSON output")
                return parsed
            except json.JSONDecodeError as exc:
                raise LLMError(f"Gemini returned invalid JSON: {exc}") from exc
            except LLMError:
                raise
            except TimeoutError as exc:
                if attempt >= attempts:
                    raise LLMError(str(exc)) from exc
                self._sleep(self._retry_delay_seconds)
            except Exception as exc:
                raise LLMError(str(exc)) from exc

        raise LLMError("Gemini provider failed without returning data")
