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
