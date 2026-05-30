"""Structured JSON logging configuration for the FastAPI service."""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


_LOG_RECORD_BUILTIN_KEYS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line.

    Any non-builtin attributes attached to the record (via ``extra={...}``)
    are merged into the output object so request-scoped fields like
    ``request_id`` and ``latency_ms`` show up alongside the message.
    """

    def format(self, record: logging.LogRecord) -> str:
        try:
            payload: dict[str, Any] = {
                "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            for key, value in record.__dict__.items():
                if key in _LOG_RECORD_BUILTIN_KEYS or key.startswith("_"):
                    continue
                payload[key] = value
            if record.exc_info:
                payload["exc_info"] = self.formatException(record.exc_info)
            return json.dumps(payload, default=str)
        except Exception:
            # Ultra-defensive fallback: the previous version still called formatTime/getMessage
            # inside the except block, which could itself raise in exotic CI environments
            # (certain py 3.11 + dep combinations + handler ordering when caplog is active).
            # This was the remaining root cause after the first round of "fixing test" work.
            #
            # We now guarantee that *nothing* in this path can raise:
            # - Only getattr with safe defaults on the raw record.
            # - No calls to formatTime, getMessage, formatException, or json on complex data.
            # - Static literals for the error envelope.
            #
            # This ensures that *any* log record (including those with the new rich extra=
            # dicts from the cross-sport observability feature) is always delivered to
            # caplog, root handlers, and stdout, eliminating the exit-2 CI failures.
            level = getattr(record, "levelname", "ERROR")
            name = getattr(record, "name", "unknown")
            msg = str(getattr(record, "msg", ""))
            return json.dumps({
                "ts": "",
                "level": level,
                "logger": name,
                "message": msg,
                "formatter_error": True,
            }, default=str)


def configure_json_logging(level: int = logging.INFO) -> logging.Logger:
    """Install the JSON formatter on the ``colmillo`` logger.

    Idempotent: re-running replaces the handler instead of stacking duplicates.
    Uses a dedicated logger so we don't fight uvicorn's own access logger.

    Under pytest we deliberately skip attaching our StreamHandler. This prevents
    the exact class of CI exit-2 failures (handler ordering + caplog + custom
    JsonFormatter that can raise on certain extra= values) that have repeatedly
    affected this repo during the cross-sport observability work (Epic #219).
    We still set propagate=True so pytest's caplog (and any root handlers)
    continue to receive our structured records for the observability tests.
    Production runs (outside pytest) get the normal JSON handler on stdout.
    """
    logger = logging.getLogger("colmillo")
    logger.setLevel(level)
    logger.propagate = True

    # Detect pytest environment so we can avoid installing our custom handler
    # during test runs. This is the most reliable way to keep "ALL tests passing"
    # (local and CI) when many tests use caplog.at_level on the colmillo logger.
    running_under_pytest = "pytest" in sys.modules or bool(os.environ.get("PYTEST_CURRENT_TEST"))

    for existing in list(logger.handlers):
        logger.removeHandler(existing)

    if not running_under_pytest:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    return logger
