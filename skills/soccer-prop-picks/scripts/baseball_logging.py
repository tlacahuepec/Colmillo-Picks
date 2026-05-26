"""MLB structured logging utilities with run_id correlation via contextvars.

Provides lifecycle logging functions that automatically attach the current
run_id to every log record, enabling full request correlation across the
collection → scoring → explanation → render pipeline.
"""

from __future__ import annotations

import logging
import os
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any


_run_context_var: ContextVar["MLBRunContext | None"] = ContextVar(
    "mlb_run_context", default=None
)

_logger = logging.getLogger("colmillo.mlb")


@dataclass(frozen=True)
class MLBRunContext:
    run_id: str
    sport: str
    league: str


def set_run_context(ctx: MLBRunContext) -> Token:
    return _run_context_var.set(ctx)


def clear_run_context(token: Token) -> None:
    _run_context_var.reset(token)


def get_current_run_id() -> str | None:
    ctx = _run_context_var.get()
    return ctx.run_id if ctx else None


def _log(level: int, message: str, **extra: Any) -> None:
    ctx = _run_context_var.get()
    fields: dict[str, Any] = {}
    if ctx:
        fields["run_id"] = ctx.run_id
        fields["sport"] = ctx.sport
        fields["league"] = ctx.league
    fields.update(extra)
    _logger.log(level, message, extra=fields)


def log_collection_start(*, home_team: str, away_team: str) -> None:
    _log(logging.INFO, "collection_start", home_team=home_team, away_team=away_team)


def log_collection_end(*, providers_ok: int, providers_failed: int, cached: int) -> None:
    _log(
        logging.INFO,
        "collection_end",
        providers_ok=providers_ok,
        providers_failed=providers_failed,
        cached=cached,
    )


def log_provider_status(
    *, provider: str, status: str, cached: bool, latency_ms: int
) -> None:
    _log(
        logging.INFO,
        "provider_status",
        provider=provider,
        status=status,
        cached=cached,
        latency_ms=latency_ms,
    )


def log_scoring_start(*, scorer_version: str, config_hash: str) -> None:
    _log(logging.INFO, "scoring_start", scorer_version=scorer_version, config_hash=config_hash)


def log_scoring_end(*, picks_generated: int, no_bet_count: int) -> None:
    _log(logging.INFO, "scoring_end", picks_generated=picks_generated, no_bet_count=no_bet_count)


def log_explanation_start(*, mode: str) -> None:
    _log(logging.INFO, "explanation_start", mode=mode)


def log_explanation_end(*, success: bool, fallback_used: bool) -> None:
    _log(logging.INFO, "explanation_end", success=success, fallback_used=fallback_used)


def log_render_start() -> None:
    _log(logging.INFO, "render_start")


def log_render_end(*, sections_rendered: int) -> None:
    _log(logging.INFO, "render_end", sections_rendered=sections_rendered)


class SecretRedactionFilter(logging.Filter):
    """Redacts known secrets from log messages and extra fields."""

    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self._secrets = [s for s in (secrets or []) if s]

    @classmethod
    def from_env(cls) -> "SecretRedactionFilter":
        secrets = []
        for key in os.environ:
            if key.upper().endswith("_API_KEY") or key.upper().endswith("_SECRET"):
                val = os.environ[key].strip()
                if val:
                    secrets.append(val)
        return cls(secrets=secrets)

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        record.msg = self._redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact(a) if isinstance(a, str) else a for a in record.args)
        for attr in list(record.__dict__):
            if attr.startswith("_") or attr in ("msg", "args", "name", "levelname", "levelno"):
                continue
            val = getattr(record, attr, None)
            if isinstance(val, str):
                redacted = self._redact(val)
                if redacted != val:
                    setattr(record, attr, redacted)
        return True

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            if secret in text:
                text = text.replace(secret, "[REDACTED]")
        return text


def safe_error_message(raw_error: str, secrets: list[str] | None = None) -> str:
    """Sanitize an error message by redacting any known secrets."""
    if not secrets:
        secrets = []
        for key in os.environ:
            if key.upper().endswith("_API_KEY") or key.upper().endswith("_SECRET"):
                val = os.environ[key].strip()
                if val:
                    secrets.append(val)
    result = raw_error
    for secret in secrets:
        if secret in result:
            result = result.replace(secret, "[REDACTED]")
    return result
