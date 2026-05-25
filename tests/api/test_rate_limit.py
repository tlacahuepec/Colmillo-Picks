"""Tests for the rate limiter."""

from __future__ import annotations

import pytest

from services.api.rate_limit import RateLimiter


class TestRateLimiterDefaults:
    def test_default_max_requests_is_300(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("COLMILLO_RATE_LIMIT_PER_HOUR", raising=False)
        limiter = RateLimiter.from_env()
        assert limiter.max_requests == 300

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("COLMILLO_RATE_LIMIT_PER_HOUR", "50")
        limiter = RateLimiter.from_env()
        assert limiter.max_requests == 50

    def test_zero_disables_limiter(self):
        limiter = RateLimiter(max_requests=0, window_seconds=3600)
        allowed, _ = limiter.check("test-key")
        assert allowed is True

    def test_rejects_after_limit_exhausted(self):
        limiter = RateLimiter(max_requests=2, window_seconds=3600)
        limiter.check("key")
        limiter.check("key")
        allowed, retry_after = limiter.check("key")
        assert allowed is False
        assert retry_after > 0
