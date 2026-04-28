"""Runtime configuration helpers for external providers."""

import os
from dataclasses import dataclass
from typing import Callable

_DEFAULT_API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
_DEFAULT_API_FOOTBALL_HOST = "v3.football.api-sports.io"


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



def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None
