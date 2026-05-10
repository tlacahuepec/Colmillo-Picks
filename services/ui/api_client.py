"""Thin HTTP client for the Colmillo-Picks API used by the Streamlit UI.

Kept separate from ``services/ui/app.py`` so it can be unit tested without
spinning up a Streamlit runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_TIMEOUT_SECONDS = 120.0


class APIError(RuntimeError):
    """Raised when the API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


@dataclass(frozen=True)
class APIClientConfig:
    base_url: str
    api_key: str
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "APIClientConfig":
        base_url = os.getenv("COLMILLO_API_URL", "http://localhost:8000").strip()
        api_key = os.getenv("COLMILLO_API_KEY", "").strip()
        return cls(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            timeout_seconds=float(os.getenv("COLMILLO_API_TIMEOUT", DEFAULT_TIMEOUT_SECONDS)),
        )


class PicksAPIClient:
    """Synchronous HTTP client for the picks API."""

    def __init__(self, config: APIClientConfig, *, transport: httpx.BaseTransport | None = None) -> None:
        self._config = config
        self._transport = transport

    # Public surface -------------------------------------------------------- #

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/healthz")

    def create_pick(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/picks", json=payload)

    def list_picks(self, *, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        return self._request("GET", "/picks", params={"limit": limit, "offset": offset})

    def get_pick(self, pick_id: str) -> dict[str, Any]:
        return self._request("GET", f"/picks/{pick_id}")

    # Internals ------------------------------------------------------------- #

    def _client(self) -> httpx.Client:
        headers = {"X-API-Key": self._config.api_key} if self._config.api_key else {}
        return httpx.Client(
            base_url=self._config.base_url,
            timeout=self._config.timeout_seconds,
            headers=headers,
            transport=self._transport,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        with self._client() as client:
            response = client.request(method, path, **kwargs)
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise APIError(response.status_code, detail)
        if not response.content:
            return {}
        return response.json()
