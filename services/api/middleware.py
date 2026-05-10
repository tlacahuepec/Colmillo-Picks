"""Authentication and request-logging middleware for the FastAPI service."""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


_API_KEY_HEADER = "X-API-Key"
# Routes that bypass the API-key requirement. Healthcheck must stay open so
# the platform (Render, docker-compose, etc.) can probe the service.
_AUTH_EXEMPT_PATHS: frozenset[str] = frozenset({"/healthz", "/docs", "/openapi.json", "/redoc"})


def _expected_api_key() -> str | None:
    value = os.getenv("COLMILLO_API_KEY", "").strip()
    return value or None


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests whose ``X-API-Key`` does not match ``COLMILLO_API_KEY``.

    If ``COLMILLO_API_KEY`` is unset the service fails closed with 503 to
    avoid accidentally exposing an open instance — except for routes in
    ``_AUTH_EXEMPT_PATHS`` (healthcheck and OpenAPI docs).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in _AUTH_EXEMPT_PATHS:
            return await call_next(request)

        expected = _expected_api_key()
        if expected is None:
            return JSONResponse(
                status_code=503,
                content={"detail": "API not configured: COLMILLO_API_KEY is unset."},
            )

        provided = request.headers.get(_API_KEY_HEADER, "").strip()
        if provided != expected:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing X-API-Key header."},
            )
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emit one structured JSON log line per HTTP request."""

    def __init__(self, app, logger: logging.Logger) -> None:
        super().__init__(app)
        self._logger = logger

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            latency_ms = max(0, round((time.perf_counter() - started) * 1000))
            self._logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                },
            )
