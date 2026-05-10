"""Optional Sentry initialization.

Only activates when ``SENTRY_DSN`` is set AND ``sentry_sdk`` is installed; both
are optional so the service runs on a vanilla install without Sentry.
"""

from __future__ import annotations

import logging
import os


def init_sentry_if_configured() -> bool:
    """Initialize Sentry when configured. Returns True if active."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk  # type: ignore[import-not-found]
        from sentry_sdk.integrations.logging import LoggingIntegration  # type: ignore[import-not-found]
    except ImportError:
        logging.getLogger("colmillo").warning(
            "SENTRY_DSN is set but sentry_sdk is not installed; skipping init."
        )
        return False
    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
        integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
    )
    return True
