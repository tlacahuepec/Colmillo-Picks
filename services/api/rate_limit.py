"""Tiny per-API-key in-memory token bucket rate limiter.

We avoid pulling in ``slowapi``/``limits`` for the MVP — single-process Render
deployments don't need a distributed limiter. If/when we scale out, swap this
for a Redis-backed implementation behind the same ``RateLimiter`` interface.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict


class RateLimiter:
    """Fixed-window limiter keyed on the caller's API key (or remote address)."""

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._counters: dict[str, list[float]] = defaultdict(list)

    @classmethod
    def from_env(cls) -> "RateLimiter":
        max_requests = int(os.getenv("COLMILLO_RATE_LIMIT_PER_HOUR", "300"))
        return cls(max_requests=max_requests, window_seconds=3600)

    def check(self, key: str) -> tuple[bool, int]:
        """Return ``(allowed, retry_after_seconds)``.

        ``retry_after_seconds`` is 0 when the request is allowed.
        """
        if self.max_requests <= 0:
            # 0 disables the limiter, useful for tests.
            return True, 0
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = [ts for ts in self._counters[key] if ts > cutoff]
            if len(timestamps) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - timestamps[0])))
                self._counters[key] = timestamps
                return False, retry_after
            timestamps.append(now)
            self._counters[key] = timestamps
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
