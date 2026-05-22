from __future__ import annotations

import os
from typing import Any, Callable

from llm.client import LLMClient, LLMError
from llm.intelligence_prompt_builder import (
    build_daily_intelligence_system_prompt,
    build_daily_intelligence_user_prompt,
)


class DailyIntelligenceError(RuntimeError):
    """Sanitized daily intelligence failure safe to show in CLI output."""


class DailyIntelligenceClient:
    """Fetches a daily soccer intelligence briefing from any LLM provider."""

    def __init__(self, *, client: LLMClient) -> None:
        self._client = client

    @classmethod
    def from_env(
        cls,
        getenv: Callable[[str], str | None] = os.getenv,
        provider: str | None = None,
    ) -> "DailyIntelligenceClient":
        resolved_provider = (
            provider
            or getenv("COLMILLO_LLM_PROVIDER")
            or "gemini"
        ).lower().strip()

        if resolved_provider == "gemini":
            api_key = getenv("GEMINI_API_KEY")
            if not api_key:
                raise DailyIntelligenceError(
                    "GEMINI_API_KEY is required. Set it in your environment before running the daily intelligence task."
                )
            from llm.gemini_client import GeminiLLMClient

            client = GeminiLLMClient(api_key=api_key, model=getenv("GEMINI_MODEL") or "gemini-2.5-flash")
        elif resolved_provider == "grok":
            api_key = getenv("XAI_API_KEY")
            if not api_key:
                raise DailyIntelligenceError(
                    "XAI_API_KEY is required. Set it in your environment before running the daily intelligence task."
                )
            from llm.grok_client import GrokLLMClient

            client = GrokLLMClient(
                api_key=api_key,
                base_url=getenv("XAI_BASE_URL") or "https://api.x.ai/v1",
                model=getenv("XAI_MODEL") or "grok-3",
            )
        elif resolved_provider == "openai":
            api_key = getenv("OPENAI_API_KEY")
            if not api_key:
                raise DailyIntelligenceError(
                    "OPENAI_API_KEY is required. Set it in your environment before running the daily intelligence task."
                )
            from llm.openai_client import OpenAILLMClient

            from openai import OpenAI

            sdk_client = OpenAI(api_key=api_key)
            client = OpenAILLMClient(sdk_client=sdk_client, model=getenv("OPENAI_MODEL") or "gpt-4.1-mini")
        else:
            raise DailyIntelligenceError(
                f"Unsupported LLM provider '{resolved_provider}'. Supported: gemini, grok, openai."
            )

        return cls(client=client)

    def fetch_daily_briefing(self, *, date_utc: str, top_n: int = 5) -> dict[str, Any]:
        system_prompt = build_daily_intelligence_system_prompt()
        user_prompt = build_daily_intelligence_user_prompt(date_utc=date_utc, top_n=top_n)
        try:
            result = self._client.generate_structured(
                system_prompt=system_prompt, user_prompt=user_prompt, schema={}
            )
        except LLMError as exc:
            raise DailyIntelligenceError(f"Daily intelligence request failed: {exc}") from exc

        if not isinstance(result, dict):
            raise DailyIntelligenceError("LLM returned a non-object response for the daily briefing")
        if "top_matches" not in result:
            raise DailyIntelligenceError(
                "Daily briefing response is missing required 'top_matches' field"
            )
        return result
