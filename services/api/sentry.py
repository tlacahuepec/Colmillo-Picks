"""Optional Sentry initialization.

Only activates when ``SENTRY_DSN`` is set AND ``sentry_sdk`` is installed; both
are optional so the service runs on a vanilla install without Sentry.
"""

from __future__ import annotations

import logging
import os


def sanitize_sentry_event(event, hint=None):
    """Sentry gets error types/frames, never requests, locals or breadcrumbs."""
    from services.api.logging_config import sanitize_diagnostics
    safe = {key: event[key] for key in ("event_id", "timestamp", "level", "release", "environment") if key in event}
    values = (event.get("exception") or {}).get("values", [])
    exceptions = []
    for value in values[:8]:
        if not isinstance(value, dict):
            continue
        entry = {"type": sanitize_diagnostics(value.get("type")), "value": "Exception detail omitted."}
        frames = (value.get("stacktrace") or {}).get("frames", [])
        safe_frames = sanitize_diagnostics({"frames": frames}, technical=True).get("frames", [])
        entry["stacktrace"] = {"frames": safe_frames}
        exceptions.append(entry)
    safe["exception"] = {"values": exceptions}
    return safe


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
        send_default_pii=False,
        include_local_variables=False,
        before_send=sanitize_sentry_event,
        before_send_transaction=lambda event, hint: None,
        before_breadcrumb=lambda breadcrumb, hint: None,
        integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
    )
    return True
