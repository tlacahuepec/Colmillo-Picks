"""Thin HTTP client for the Colmillo-Picks API used by the Streamlit UI.

Kept separate from ``services/ui/app.py`` so it can be unit tested without
spinning up a Streamlit runtime.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx


DEFAULT_TIMEOUT_SECONDS = 120.0
TERMINAL_STATUSES = frozenset({"success", "failed"})


class APIError(RuntimeError):
    """Raised when the API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


class PickTimeoutError(RuntimeError):
    """Raised when ``wait_for_pick`` polls past its deadline."""


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
        """POST a pick request. Returns the ``202`` accepted body
        ``{id, status, created_at}``; the caller polls ``get_pick_status``
        (or uses ``wait_for_pick``) for completion."""
        return self._request("POST", "/picks", json=payload)

    def discover_matches(
        self,
        *,
        date: str,
        sports: list[str],
        limit_per_sport: int = 5,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "date": date,
            "sports": sports,
            "limit_per_sport": limit_per_sport,
        }
        if llm_provider:
            payload["llm_provider"] = llm_provider
        if llm_model:
            payload["llm_model"] = llm_model
        return self._request("POST", "/matches/discover", json=payload)

    def list_picks(self, *, limit: int = 20, offset: int = 0, sport: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if sport:
            params["sport"] = sport
        return self._request("GET", "/picks", params=params)

    def get_pick(self, pick_id: str) -> dict[str, Any]:
        return self._request("GET", f"/picks/{pick_id}")

    def get_pick_status(self, pick_id: str) -> dict[str, Any]:
        return self._request("GET", f"/picks/{pick_id}/status")

    def wait_for_pick(
        self,
        pick_id: str,
        *,
        timeout_seconds: float = 120.0,
        poll_interval_seconds: float = 1.5,
        sleep=time.sleep,
    ) -> dict[str, Any]:
        """Poll ``/picks/{id}/status`` until terminal or timeout."""
        deadline = time.monotonic() + timeout_seconds
        while True:
            status = self.get_pick_status(pick_id)
            if status.get("status") in TERMINAL_STATUSES:
                return status
            if time.monotonic() >= deadline:
                raise PickTimeoutError(
                    f"Pick {pick_id} did not finish within {timeout_seconds}s "
                    f"(last status: {status.get('status')})"
                )
            sleep(poll_interval_seconds)

    def record_outcomes(self, pick_id: str, outcomes: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/picks/{pick_id}/outcomes",
            json={"outcomes": outcomes},
        )

    def get_outcomes(self, pick_id: str) -> dict[str, Any]:
        return self._request("GET", f"/picks/{pick_id}/outcomes")

    def get_hit_rate(self, *, since: str | None = None) -> dict[str, Any]:
        params = {"since": since} if since else None
        return self._request("GET", "/stats/hit-rate", params=params)

    def check_availability(
        self, pick_id: str, *, platforms: list[str] | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if platforms:
            payload["platforms"] = platforms
        return self._request("POST", f"/picks/{pick_id}/availability", json=payload)

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
