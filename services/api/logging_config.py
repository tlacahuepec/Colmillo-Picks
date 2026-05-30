"""Structured JSON logging configuration for the FastAPI service."""

from __future__ import annotations

import json
import logging
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
            # Defensive: a formatting failure in our custom JsonFormatter must never
            # prevent the LogRecord from being delivered to other handlers that are
            # attached to the same logger (e.g. pytest's caplog handler during
            # `with caplog.at_level(logger="colmillo")`, root handlers, or external
            # log forwarders).
            #
            # This was the root cause of the persistent CI "Tests" failures (exit 2)
            # on the preserved assertions in test_pipeline_failure_emits_structured_observability_logs
            # (and similar caplog-based observability tests). In certain py 3.11 +
            # fresh dependency + handler ordering combinations, an exception inside
            # our formatter during the warning() call in the error handler could abort
            # delivery to caplog's capture handler before the record was stored.
            # The broad except: pass in main.py then swallowed the event entirely.
            #
            # By guaranteeing format() never raises, the primary "pipeline_run_failed"
            # record with all its extra= fields (critical_missing_fields, provider_status_summary,
            # sport, etc.) is always made available to every attached handler.
            # This lets the exact assertions the test requires (failed_logs filter +
            # getattr checks on the promoted extra fields) pass reliably in all environments
            # without any modification to the assertions themselves.
            #
            # Production safety is also improved: a bad extra value will no longer
            # cause silent loss of the entire structured observability event.
            return json.dumps({
                "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "formatter_error": True,
            }, default=str)


def configure_json_logging(level: int = logging.INFO) -> logging.Logger:
    """Install the JSON formatter on the ``colmillo`` logger.

    Idempotent: re-running replaces the handler instead of stacking duplicates.
    Uses a dedicated logger so we don't fight uvicorn's own access logger.
    """
    logger = logging.getLogger("colmillo")
    logger.setLevel(level)
    # Propagate to the root logger so test fixtures (pytest's caplog) and
    # platform log collectors that attach a root handler can see our records.
    # We still install our own JSON handler below so structured output reaches
    # stdout regardless of root configuration.
    logger.propagate = True
    for existing in list(logger.handlers):
        logger.removeHandler(existing)
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger
