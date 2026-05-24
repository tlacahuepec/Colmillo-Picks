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

from services.api.rate_limit import RateLimiter


_API_KEY_HEADER = "X-API-Key"
# Routes that bypass the API-key requirement. Healthcheck must stay open so
# the platform (Render, docker-compose, etc.) can probe the service.
_AUTH_EXEMPT_PATHS: frozenset[str] = frozenset({"/healthz", "/version", "/docs", "/openapi.json", "/redoc"})


def _expected_api_key() -> str | None:
    value = os.getenv("COLMILLO_API_KEY", "").strip()
    return value or None


def _admin_api_key() -> str | None:
    value = os.getenv("COLMILLO_ADMIN_API_KEY", "").strip()
    return value or None


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests whose ``X-API-Key`` does not match ``COLMILLO_API_KEY``.

    Also enforces a per-key rate limit (configured via
    ``COLMILLO_RATE_LIMIT_PER_HOUR``; default 30; 0 disables). Admin routes
    additionally require ``COLMILLO_ADMIN_API_KEY`` to match.
    """

    def __init__(self, app, *, rate_limiter: RateLimiter | None = None) -> None:
        super().__init__(app)
        self._rate_limiter = rate_limiter or RateLimiter.from_env()

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

        # Admin routes require an additional admin key.
        if request.url.path.startswith("/admin"):
            admin_key = _admin_api_key()
            if admin_key is None:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Admin not configured: COLMILLO_ADMIN_API_KEY is unset."},
                )
            provided_admin = request.headers.get("X-Admin-API-Key", "").strip()
            if provided_admin != admin_key:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Invalid or missing X-Admin-API-Key header."},
                )

        allowed, retry_after = self._rate_limiter.check(provided)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded.", "retry_after_seconds": retry_after},
                headers={"Retry-After": str(retry_after)},
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
