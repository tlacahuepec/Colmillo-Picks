from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.request import urlopen

from llm.intelligence_prompt_builder import (
    build_daily_intelligence_system_prompt,
    build_daily_intelligence_user_prompt,
)
from llm_fixture_provider import LLMFixtureProviderError, OpenAICompatibleChatClient

_DEFAULT_GROK_MODEL = "grok-3"
_DEFAULT_XAI_BASE_URL = "https://api.x.ai/v1"


class GrokDailyIntelligenceError(RuntimeError):
    """Sanitized daily intelligence failure safe to show in CLI output."""


class GrokDailyIntelligenceClient:
    """Fetches a daily soccer intelligence briefing from Grok using live web search."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 60,
        urlopen_fn: Callable[..., Any] = urlopen,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self._client = OpenAICompatibleChatClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            urlopen_fn=urlopen_fn,
        )

    @classmethod
    def from_env(
        cls,
        getenv: Callable[[str], str | None] = os.getenv,
    ) -> "GrokDailyIntelligenceClient":
        api_key = getenv("XAI_API_KEY")
        if not api_key:
            raise GrokDailyIntelligenceError(
                "XAI_API_KEY is required. Set it in your environment before running the daily intelligence task."
            )
        return cls(
            api_key=api_key,
            base_url=getenv("XAI_BASE_URL") or _DEFAULT_XAI_BASE_URL,
            model=getenv("XAI_MODEL") or _DEFAULT_GROK_MODEL,
        )

    def fetch_daily_briefing(self, *, date_utc: str, top_n: int = 5) -> dict[str, Any]:
        system_prompt = build_daily_intelligence_system_prompt()
        user_prompt = build_daily_intelligence_user_prompt(date_utc=date_utc, top_n=top_n)
        try:
            result = self._client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
        except LLMFixtureProviderError as exc:
            raise GrokDailyIntelligenceError(f"Daily intelligence request failed: {exc}") from exc

        if not isinstance(result, dict):
            raise GrokDailyIntelligenceError("Grok returned a non-object response for the daily briefing")
        if "top_matches" not in result:
            raise GrokDailyIntelligenceError(
                "Daily briefing response is missing required 'top_matches' field"
            )
        return result
