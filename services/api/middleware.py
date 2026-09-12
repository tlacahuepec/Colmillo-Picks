"""Authentication and request-logging middleware for the FastAPI service."""

from __future__ import annotations

import hmac
import logging
import os
import re
import time
import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from services.api.rate_limit import RateLimiter
from services.api.logging_config import valid_request_id
from services.diagnostics import request_context


_API_KEY_HEADER = "X-API-Key"
# Routes that bypass the API-key requirement. Healthcheck must stay open so
# the platform (Render, docker-compose, etc.) can probe the service.
_AUTH_EXEMPT_PATHS: frozenset[str] = frozenset({"/healthz", "/version", "/docs", "/openapi.json", "/redoc"})


def _is_diagnostics(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in ("/diagnostics", "/admin/diagnostics"))


def _is_polling(method: str, path: str) -> bool:
    return method in {"GET", "HEAD"} and (
        path in {"/healthz", "/version"}
        or re.fullmatch(r"/(?:picks|slates)/[^/]+/status/?", path) is not None
    )


def _emit_request(**metadata) -> None:
    try:
        from services.diagnostics import emit, get_store, operation
        status_code = metadata["status_code"]
        get_store().count("http_requests")
        if status_code < 400:
            return  # Business workflows already own their operation records.
        get_store().count("http_errors")
        metadata["route"] = metadata.pop("path")
        duration_ms = metadata.pop("latency_ms")
        with operation("http_request", **metadata) as op:
            emit("http.request.failed", stage="api", level="ERROR" if status_code >= 500 else "WARNING",
                 outcome="failed", duration_ms=duration_ms, **metadata)
            op.finish("failed", status_code=status_code)
    except Exception:
        pass  # The stdout record remains available when diagnostics is offline.


def _expected_api_key() -> str | None:
    value = os.getenv("COLMILLO_API_KEY", "").strip()
    return value or None


def _admin_api_key() -> str | None:
    value = os.getenv("COLMILLO_ADMIN_API_KEY", "").strip()
    return value or None


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests whose ``X-API-Key`` does not match ``COLMILLO_API_KEY``.

    Also enforces a per-key rate limit (configured via
    ``COLMILLO_RATE_LIMIT_PER_HOUR``; default 300; 0 disables). Admin routes
    additionally require ``COLMILLO_ADMIN_API_KEY`` to match.
    """

    def __init__(self, app, *, rate_limiter: RateLimiter | None = None) -> None:
        super().__init__(app)
        self._rate_limiter = rate_limiter or RateLimiter.from_env()
        self._diagnostics_read_limiter = RateLimiter(max_requests=120, window_seconds=60)
        self._diagnostics_write_limiter = RateLimiter(max_requests=10, window_seconds=60)

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
        if not hmac.compare_digest(provided.encode(), expected.encode()):
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
            if not hmac.compare_digest(provided_admin.encode(), admin_key.encode()):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Invalid or missing X-Admin-API-Key header."},
                )

        limiter = self._rate_limiter
        if _is_diagnostics(request.url.path):
            expensive = request.method not in {"GET", "HEAD", "OPTIONS"} or request.url.path.rstrip("/").endswith("/export")
            limiter = self._diagnostics_write_limiter if expensive else self._diagnostics_read_limiter
        allowed, retry_after = limiter.check(provided)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded.", "retry_after_seconds": retry_after},
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        if _is_diagnostics(request.url.path):
            response.headers["Cache-Control"] = "no-store"
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emit one structured JSON log line per HTTP request."""

    def __init__(self, app, logger: logging.Logger) -> None:
        super().__init__(app)
        self._logger = logger

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied_id = request.headers.get("X-Request-Id")
        request_id = supplied_id if valid_request_id(supplied_id) else uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500
        diagnostics = _is_diagnostics(request.url.path)
        polling = _is_polling(request.method, request.url.path)

        async def invoke() -> Response:
            nonlocal status_code
            try:
                response = await call_next(request)
                status_code = response.status_code
                response.headers["X-Request-Id"] = request_id
                return response
            finally:
                latency_ms = max(0, round((time.perf_counter() - started) * 1000))
                route = request.scope.get("route")
                # Route templates avoid recording raw URLs, query strings and
                # user-controlled path segments, including on unmatched routes.
                path = getattr(route, "path", "/unmatched")
                metadata = {
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                }
                if not diagnostics:
                    try:
                        from services.diagnostics import get_store
                        store = get_store()
                        bucket = "lt_100ms" if latency_ms < 100 else "lt_1s" if latency_ms < 1000 else "gte_1s"
                        store.count("latency_" + bucket)
                        if polling and status_code < 400 and latency_ms < 1000:
                            store.count("suppressed_polls")
                    except Exception:
                        pass  # Diagnostics must not replace a successful response.
                if not ((diagnostics or polling) and status_code < 400 and latency_ms < 1000):
                    self._logger.log(
                        logging.ERROR if status_code >= 500 else logging.INFO,
                        "request", extra={**metadata, "diagnostics_skip": True},
                    )
                    # Reading diagnostics must not alter the metrics it shows.
                    if not diagnostics:
                        _emit_request(**metadata)

        with request_context(request_id):
            return await invoke()
