"""Bounded, allowlisted JSON logging and diagnostics serialization."""

from __future__ import annotations

import json
import logging
import math
import os
import re
import sys
from typing import Any

from services.diagnostics import public_trace, safe_metadata, safe_text, valid_id


# Unknown fields are discarded before formatting or object serialization.
_SAFE_FIELDS = frozenset({
    "id", "operation_id", "parent_id", "parent_operation_id", "request_id",
    "event_id", "sequence", "seq", "event", "kind", "type", "stage", "level",
    "outcome", "status", "sport", "provider", "model", "component", "action",
    "method", "path", "route", "status_code", "latency_ms", "duration_ms",
    "created_at", "updated_at", "started_at", "finished_at", "ended_at",
    "timestamp", "ts", "expires_at", "debug_until", "debug_expires_at",
    "pick_id", "slate_id", "run_id", "job_id", "error_type", "error_code",
    "attempt", "retry_count", "count", "event_count", "operation_count",
    "dropped_events", "dropped_operations", "dropped_count", "queue_depth",
    "queue_size", "queue_capacity", "capacity", "max_events", "max_operations",
    "retention_seconds", "retention_days", "ttl_seconds", "healthy", "enabled",
    "available", "degraded", "debug", "truncated", "complete", "completeness",
    "metadata", "counts", "counters", "metrics", "stages", "health",
    "version", "schema_version", "commit", "build_time", "channel",
    "success", "failure", "error", "warning", "pending", "running",
    "completed", "failed", "cancelled", "total", "retained", "dropped",
    "summary", "service", "home_team", "away_team", "parent_span", "span_id",
    "exception_type", "cause_types", "http_status", "retryable",
    "details_days", "summaries_days", "storage_budget_bytes", "collection_enabled",
    "write_failures", "storage_pruned", "truncated_events", "http_requests", "http_errors",
    "latency_lt_100ms", "latency_lt_1s", "latency_gte_1s", "suppressed_polls", "console_failures", "storage_budget_reached",
    "file", "function", "line",
})
_LOG_FIELDS = _SAFE_FIELDS - {"error"}
_CODE = re.compile(r"[A-Za-z0-9_./:{} -]{1,200}\Z")
_TEXT_FIELDS = frozenset({
    "created_at", "updated_at", "started_at", "finished_at", "ended_at",
    "timestamp", "ts", "expires_at", "debug_until", "debug_expires_at", "build_time",
})
_SECRET = re.compile(
    r"(?i)(?:bearer\s|api[_-]?key|password|secret|token[=:]|https?://|@|sk-[a-z0-9])"
)


def safe_code(value: Any, default: str = "redacted") -> str:
    """Accept bounded operational labels without object stringification."""
    if type(value) is str and _CODE.fullmatch(value) and not _SECRET.search(value):
        return safe_text(value, 200)
    return default


def valid_request_id(value: Any) -> bool:
    return type(value) is str and valid_id(value)


def _safe_frames(value: Any) -> list[dict[str, Any]]:
    frames = []
    if type(value) is not list:
        return frames
    for frame in value[-50:]:
        if type(frame) is not dict:
            continue
        item = {}
        for key in ("function", "module", "lineno", "in_app", "line"):
            if key in frame:
                item[key] = sanitize_diagnostics(frame[key])
        # Never publish absolute filesystem paths, source lines, or local vars.
        filename = frame.get("filename", frame.get("file"))
        if type(filename) is str:
            item["file" if "file" in frame else "filename"] = safe_code(filename.replace("\\", "/").rsplit("/", 1)[-1])
        frames.append(item)
    return frames


def sanitize_diagnostics(value: Any, *, technical: bool = False, _depth: int = 0) -> Any:
    """Build a JSON-safe copy; unknown objects are never traversed or formatted."""
    if _depth > 6:
        return None
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        return value if math.isfinite(value) else None
    if type(value) is str:
        return safe_code(value)
    if type(value) is list or type(value) is tuple:
        return [sanitize_diagnostics(v, technical=technical, _depth=_depth + 1) for v in value[:100]]
    if type(value) is not dict:
        return None
    result = {}
    for key, item in value.items():
        if type(key) is not str:
            continue
        if key == "metadata":
            result[key] = safe_metadata(item, include_frames=technical)
        elif key == "summary" and type(item) is str:
            result[key] = safe_text(item, 512)
        elif technical and key == "frames":
            result[key] = _safe_frames(item)
        elif technical and key in {"stacktrace", "exception", "exceptions", "values"}:
            result[key] = sanitize_diagnostics(item, technical=True, _depth=_depth + 1)
        elif key in _SAFE_FIELDS:
            if key in _TEXT_FIELDS and type(item) is str:
                result[key] = item if re.fullmatch(r"[0-9TZtz+: .-]{1,40}", item) else "redacted"
            elif key == "error" and type(item) is str:
                continue
            else:
                result[key] = sanitize_diagnostics(item, technical=technical, _depth=_depth + 1)
    return result if technical else public_trace(result)


class JsonFormatter(logging.Formatter):
    """Format only approved primitive fields and static event names."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            # getMessage() would interpolate potentially sensitive objects.
            payload: dict[str, Any] = {
                "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
                "level": safe_code(record.levelname, "ERROR"),
                "logger": safe_code(record.name, "unknown"),
                "message": safe_code(record.msg) if (
                    not record.args and type(record.msg) is str
                    and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}", record.msg)
                ) else "log_event",
            }
            for key in _LOG_FIELDS:
                if key in record.__dict__:
                    payload[key] = sanitize_diagnostics({key: record.__dict__[key]})[key]
            if record.exc_info and isinstance(record.exc_info, tuple):
                exc_type = record.exc_info[0]
                if isinstance(exc_type, type):
                    payload["error_type"] = safe_code(exc_type.__name__)
            return json.dumps(payload, allow_nan=False)
        except Exception:
            # Static fallback: never re-read, stringify, or format the record.
            return '{"level":"ERROR","message":"log_format_failed","formatter_error":true}'


def configure_json_logging(level: int = logging.INFO) -> logging.Logger:
    """Install one stdout handler; preserve caplog capture under pytest."""
    logger = logging.getLogger("colmillo")
    logger.setLevel(level)
    running_under_pytest = "pytest" in sys.modules or bool(os.environ.get("PYTEST_CURRENT_TEST"))
    # Root handlers would print unsanitized records and duplicate every line.
    logger.propagate = running_under_pytest
    # Middleware owns access logs, including healthy polling suppression.
    logging.getLogger("uvicorn.access").disabled = True
    for existing in list(logger.handlers):
        logger.removeHandler(existing)
    if not running_under_pytest:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        # Route remaining application/SDK console records through the same policy.
        root = logging.getLogger()
        for old in list(root.handlers):
            root.removeHandler(old)
        root.addHandler(handler)
        root.setLevel(level)
        # Uvicorn installs a non-propagating handler before importing the app;
        # redirect it too so uncaught server exceptions cannot bypass redaction.
        for name in ("uvicorn", "uvicorn.error"):
            server_logger = logging.getLogger(name)
            for old in list(server_logger.handlers):
                server_logger.removeHandler(old)
            server_logger.propagate = True
    return logger
