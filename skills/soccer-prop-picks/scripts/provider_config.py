"""Runtime configuration helpers for external providers."""

import os
from dataclasses import dataclass
from typing import Callable

_DEFAULT_API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
_DEFAULT_API_FOOTBALL_HOST = "v3.football.api-sports.io"
_DEFAULT_OPENAI_COMPATIBLE_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_XAI_BASE_URL = "https://api.x.ai/v1"
_DEFAULT_OPENAI_FIXTURE_MODEL = "gpt-4.1-mini"
_DEFAULT_GEMINI_FIXTURE_MODEL = "gemini-2.5-flash"


@dataclass(frozen=True)
class ApiFootballProviderConfig:
    """Resolved API-Football runtime configuration."""

    api_key: str | None
    base_url: str
    host: str

    @classmethod
    def from_env(cls, getenv: Callable[[str], str | None] = os.getenv) -> "ApiFootballProviderConfig":
        api_key = _clean(getenv("API_FOOTBALL_API_KEY"))
        base_url = _clean(getenv("API_FOOTBALL_BASE_URL")) or _DEFAULT_API_FOOTBALL_BASE_URL
        host = _clean(getenv("API_FOOTBALL_HOST")) or _DEFAULT_API_FOOTBALL_HOST
        return cls(api_key=api_key, base_url=base_url, host=host)

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("Missing credentials for provider 'api-football'. Set API_FOOTBALL_API_KEY.")
        if not self.base_url:
            raise ValueError("Invalid API-Football config. Set API_FOOTBALL_BASE_URL to a non-empty URL.")
        if not self.host:
            raise ValueError("Invalid API-Football config. Set API_FOOTBALL_HOST to a non-empty host.")


@dataclass(frozen=True)
class LLMFixtureProviderConfig:
    """Resolved runtime config for LLM-backed fixture lookup."""

    provider: str
    api_key: str | None
    base_url: str | None
    model: str | None

    @classmethod
    def from_env(
        cls,
        getenv: Callable[[str], str | None] = os.getenv,
        *,
        provider: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> "LLMFixtureProviderConfig":
        resolved_provider = _clean(provider) or _clean(getenv("SOCCER_FIXTURE_LLM_PROVIDER")) or _infer_llm_provider(getenv)
        normalized_provider = _normalize_llm_provider(resolved_provider)
        api_key = _clean(getenv("SOCCER_FIXTURE_LLM_API_KEY")) or _provider_api_key(normalized_provider, getenv)
        resolved_base_url = _clean(base_url) or _clean(getenv("SOCCER_FIXTURE_LLM_BASE_URL")) or _provider_base_url(
            normalized_provider,
            getenv,
        )
        resolved_model = _clean(model) or _clean(getenv("SOCCER_FIXTURE_LLM_MODEL")) or _provider_model(
            normalized_provider,
            getenv,
        )
        return cls(
            provider=normalized_provider,
            api_key=api_key,
            base_url=resolved_base_url,
            model=resolved_model,
        )

    def is_configured(self) -> bool:
        if self.provider == "gemini":
            return bool(self.api_key and self.model)
        return bool(self.api_key and self.base_url and self.model)

    def validate(self) -> None:
        if self.provider not in {"openai", "xai", "gemini", "openai-compatible"}:
            raise ValueError(
                "Unsupported fixture LLM provider "
                f"'{self.provider}'. Supported values: openai, xai, gemini, openai-compatible."
            )
        if not self.api_key:
            raise ValueError(
                "Missing credentials for fixture LLM provider. Set SOCCER_FIXTURE_LLM_API_KEY "
                "or a provider-specific key such as OPENAI_API_KEY, XAI_API_KEY, or GROK_API_KEY."
            )
        if not self.base_url:
            raise ValueError("Invalid fixture LLM config. Set SOCCER_FIXTURE_LLM_BASE_URL to a non-empty URL.")
        if not self.model:
            raise ValueError("Invalid fixture LLM config. Set SOCCER_FIXTURE_LLM_MODEL to a non-empty model name.")


def _infer_llm_provider(getenv: Callable[[str], str | None]) -> str:
    if _clean(getenv("OPENAI_API_KEY")):
        return "openai"
    if _clean(getenv("XAI_API_KEY")) or _clean(getenv("GROK_API_KEY")):
        return "xai"
    if _clean(getenv("GEMINI_API_KEY")):
        return "gemini"
    return "openai-compatible"


def _normalize_llm_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized in {"grok", "x-ai"}:
        return "xai"
    if normalized == "google":
        return "gemini"
    return normalized


def _provider_api_key(provider: str, getenv: Callable[[str], str | None]) -> str | None:
    if provider == "openai":
        return _clean(getenv("OPENAI_API_KEY"))
    if provider == "xai":
        return _clean(getenv("XAI_API_KEY")) or _clean(getenv("GROK_API_KEY"))
    if provider == "gemini":
        return _clean(getenv("GEMINI_API_KEY"))
    return None


def _provider_base_url(provider: str, getenv: Callable[[str], str | None]) -> str | None:
    if provider == "openai":
        return _clean(getenv("OPENAI_BASE_URL")) or _DEFAULT_OPENAI_COMPATIBLE_BASE_URL
    if provider == "xai":
        return _clean(getenv("XAI_BASE_URL")) or _clean(getenv("GROK_BASE_URL")) or _DEFAULT_XAI_BASE_URL
    if provider == "gemini":
        return "https://generativelanguage.googleapis.com"
    return None


def _provider_model(provider: str, getenv: Callable[[str], str | None]) -> str | None:
    if provider == "openai":
        return _clean(getenv("OPENAI_MODEL")) or _DEFAULT_OPENAI_FIXTURE_MODEL
    if provider == "xai":
        return _clean(getenv("XAI_MODEL")) or _clean(getenv("GROK_MODEL"))
    if provider == "gemini":
        return _clean(getenv("GEMINI_MODEL")) or _DEFAULT_GEMINI_FIXTURE_MODEL
    return None



def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None
