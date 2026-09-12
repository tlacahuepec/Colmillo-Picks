"""Governed raw provider archive with redaction and bounded retention."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


ARCHIVE_WARNING = "Provider source archive; may contain unverified or sensitive source material."
_SECRET_KEYS = re.compile(r"(authorization|api[_-]?key|token|secret|password|cookie|session|signature|sig)", re.I)
_SIGNED_QUERY = re.compile(r"([?&](?:token|sig|signature|key|expires)=[^&]*)", re.I)


@dataclass(frozen=True)
class ArchivePolicy:
    max_bytes: int = 2_000_000
    retention_days: int = 180


def redact_archive(value: Any) -> Any:
    """Return JSON-safe source content with secret-like fields removed."""
    if isinstance(value, Mapping):
        return {str(key): "[REDACTED]" if _SECRET_KEYS.search(str(key)) else redact_archive(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact_archive(item) for item in value]
    if isinstance(value, tuple):
        return [redact_archive(item) for item in value]
    if isinstance(value, str):
        return _SIGNED_QUERY.sub("", value)
    if value is None or type(value) in (str, int, float, bool):
        return value
    return str(value)


def prepare_archive(payload: Any, *, policy: ArchivePolicy = ArchivePolicy()) -> tuple[str, str]:
    redacted = redact_archive(payload)
    encoded = json.dumps(redacted, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > policy.max_bytes:
        raise ValueError("raw archive payload exceeds configured size limit")
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return digest, encoded


def archive_expiry(created_at: str, policy: ArchivePolicy = ArchivePolicy()) -> str:
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return (created + timedelta(days=policy.retention_days)).isoformat().replace("+00:00", "Z")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
