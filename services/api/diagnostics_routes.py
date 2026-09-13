"""Authenticated diagnostics routers; mount both routers in the app factory.

The shared store owns retention, cleanup, operation contexts and persistence.
This module only reads bounded snapshots and accepts a small UI event vocabulary.
"""

from __future__ import annotations

import hmac
import io
import json
import os
import zipfile
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from services.api.logging_config import sanitize_diagnostics
from services.diagnostics import MESSAGES, public_trace, safe_metadata, safe_text


ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
OperationId = Annotated[str, Path(min_length=1, max_length=64, pattern=ID_PATTERN)]
CorrelationId = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=ID_PATTERN)]
EXPORT_LIMIT = 500
SCHEMA_VERSION = 1


def _authenticate(request: Request) -> None:
    """Fail closed even when a host mounts the router without auth middleware."""
    expected = os.getenv("COLMILLO_API_KEY", "").strip()
    if not expected:
        raise HTTPException(503, "API authentication is not configured.")
    provided = request.headers.get("X-API-Key", "").strip()
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(401, "Invalid or missing X-API-Key header.")


def _authenticate_admin(request: Request) -> None:
    expected = os.getenv("COLMILLO_ADMIN_API_KEY", "").strip()
    if not expected:
        raise HTTPException(503, "Admin authentication is not configured.")
    provided = request.headers.get("X-Admin-API-Key", "").strip()
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(403, "Invalid or missing X-Admin-API-Key header.")


router = APIRouter(prefix="/diagnostics", tags=["diagnostics"], dependencies=[Depends(_authenticate)])
admin_router = APIRouter(
    prefix="/admin/diagnostics", tags=["diagnostics"],
    dependencies=[Depends(_authenticate), Depends(_authenticate_admin)],
)


def get_store() -> Any:
    # Lazy import allows the API to start while the optional store is unavailable.
    try:
        from services.diagnostics import get_store as shared_get_store
    except ImportError:
        raise HTTPException(503, "Diagnostics are unavailable.") from None
    return shared_get_store()


def emit(event: str, **kwargs: Any) -> bool:
    try:
        from services.diagnostics import emit as shared_emit
    except ImportError:
        raise HTTPException(503, "Diagnostics are unavailable.") from None
    return shared_emit(event, **kwargs)


def _legacy_operation(ident: str) -> dict | None:
    """Recover a bounded business summary without loading/exporting raw trace data."""
    from sqlalchemy.exc import SQLAlchemyError
    from services.api import db

    for getter, kind in ((db.get_pick_run, "pick"), (db.get_slate_run, "slate")):
        try:
            row = getter(ident)
        except (SQLAlchemyError, OSError):
            continue
        if row is None:
            continue
        raw = getattr(row, "diagnostics_json", None)
        try:
            saved = json.loads(raw) if type(raw) is str and len(raw) <= 65_536 else {}
        except (ValueError, TypeError):
            saved = {}
        if type(saved) is not dict:
            saved = {}
        outcome = getattr(row, "outcome", None) or saved.get("outcome") or getattr(row, "status", "unknown")
        created_at = getattr(row, "created_at", None)
        metadata = safe_metadata({
            **saved, f"{kind}_id": row.id, "sport": getattr(row, "sport", None),
            "stage": getattr(row, "error_stage", None),
        }, include_frames=False)
        return public_trace({
            "operation_id": getattr(row, "operation_id", None) or row.id,
            "service": "api", "kind": kind, "outcome": outcome,
            "sport": getattr(row, "sport", None),
            "started_at": created_at.isoformat() if isinstance(created_at, datetime) else None,
            "duration_ms": getattr(row, "latency_ms", None),
            "summary": safe_text(saved.get("summary") or MESSAGES.get(outcome, "Only the saved business record is available."), 512),
            "completeness": "legacy_summary_only", "metadata": metadata, "event_count": 0,
        })
    return None


def _operation(store: Any, operation_id: str) -> dict:
    resolved = store.resolve(operation_id)
    operation = store.get_operation(resolved)
    if operation is None:
        operation = _legacy_operation(operation_id)
        if operation is None and resolved != operation_id:
            operation = _legacy_operation(resolved)
        if operation is not None:
            operation = store.get_operation(operation["operation_id"]) or operation
    if operation is None:
        raise HTTPException(404, "Operation not found.")
    return operation


def _snapshot(store: Any, operation: dict, limit: int, offset: int = 0, *, technical: bool = False) -> tuple[list, dict]:
    # One lookahead record detects truncation without an unbounded count/query.
    operation_id = operation["operation_id"]
    records = store.events(operation_id, limit=min(limit + 1, EXPORT_LIMIT), offset=offset)
    has_more = len(records) > limit
    if limit == EXPORT_LIMIT and len(records) == limit:
        has_more = bool(store.events(operation_id, limit=1, offset=offset + limit))
    events = [sanitize_diagnostics(row, technical=technical) for row in records[:limit]]
    status = operation.get("completeness", "unknown")
    if store.health().get("counters", {}).get("dropped_events") and status == "complete":
        status = "possibly_incomplete"
    if status == "complete" and has_more:
        status = "truncated"
    return events, {
        "status": safe_text(status),
        "complete": status == "complete" and offset == 0 and operation.get("outcome") not in {"running", "queued", "pending"},
        "events_returned": len(events), "has_more": has_more, "truncated": has_more or status == "truncated",
        "offset": offset, "limit": limit, "scope": "retained_events",
        "snapshot": True, "retention_may_apply": True,
    }


@router.get("/operations")
def list_operations(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    sport: Annotated[str | None, Query(max_length=64, pattern=ID_PATTERN)] = None,
    service: Annotated[str | None, Query(max_length=64, pattern=ID_PATTERN)] = None,
    outcome: Annotated[str | None, Query(max_length=64, pattern=ID_PATTERN)] = None,
    operation_id: Annotated[str | None, Query(max_length=64, pattern=ID_PATTERN)] = None,
    since: Annotated[datetime | None, Query()] = None,
    store: Any = Depends(get_store),
) -> dict:
    filters = {key: value for key, value in {
        "sport": sport, "service": service, "outcome": outcome, "operation_id": operation_id,
        "since": (since.replace(tzinfo=since.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat() if since else None),
    }.items() if value is not None}
    items = store.list_operations(limit=limit, offset=offset, **filters)
    if not items and operation_id and offset == 0:
        legacy = _legacy_operation(operation_id)
        if legacy and all(legacy.get(key) == value for key, value in filters.items() if key in {"sport", "service", "outcome"}):
            if not since or (legacy.get("started_at") and legacy["started_at"] >= filters["since"]):
                items = [legacy]
    return {"items": [sanitize_diagnostics(row) for row in items[:limit]], "limit": limit, "offset": offset}


@router.get("/operations/{operation_id}")
def operation_detail(operation_id: OperationId, store: Any = Depends(get_store)) -> dict:
    operation = _operation(store, operation_id)
    events, completeness = _snapshot(store, operation, 100)
    return {"operation": sanitize_diagnostics(operation), "events": events, "completeness": completeness}


@router.get("/operations/{operation_id}/events")
def operation_events(
    operation_id: OperationId,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    store: Any = Depends(get_store),
) -> dict:
    operation = _operation(store, operation_id)
    events, completeness = _snapshot(store, operation, limit, offset)
    return {"items": events, "limit": limit, "offset": offset, "completeness": completeness}


@router.get("/operations/{operation_id}/export")
def export_operation(operation_id: OperationId, request: Request, store: Any = Depends(get_store)) -> Response:
    operation = sanitize_diagnostics(_operation(store, operation_id))
    events, completeness = _snapshot(store, operation, EXPORT_LIMIT)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "app_version": sanitize_diagnostics(operation.get("metadata", {}).get("version") or request.app.version),
        "sanitized": True, "includes_technical_frames": False,
        "event_limit": EXPORT_LIMIT, "completeness": completeness,
        "configuration": {"diagnostics_enabled": os.getenv("COLMILLO_DIAGNOSTICS_ENABLED", "1") != "0",
                          "external_worker": os.getenv("COLMILLO_WORKER_MODE") == "external",
                          "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
                          "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
                          "grok_configured": bool(os.getenv("XAI_API_KEY"))},
    }
    summary = (
        f"Diagnostics export (schema {SCHEMA_VERSION})\n"
        f"Operation: {operation_id}\n"
        f"Outcome: {operation.get('outcome', 'unknown')}\n"
        f"Summary: {operation.get('summary', 'Unavailable')}\n"
        f"Completeness: {completeness['status']}\n"
        f"Events included: {len(events)} (maximum {EXPORT_LIMIT})\n"
        f"Truncated: {completeness['truncated']}\n"
        "Sanitized: yes; technical frames: excluded.\n"
        "This is a snapshot of retained events. Retention or dropped events may\n"
        "mean earlier records are unavailable; active operations may add events.\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, value in (("manifest.json", manifest), ("operation.json", operation), ("events.json", events)):
            archive.writestr(filename, json.dumps(value, ensure_ascii=True, allow_nan=False, indent=2))
        archive.writestr("summary.txt", summary)
    return Response(buffer.getvalue(), media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="diagnostics-{operation_id}.zip"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


@router.get("/health")
def diagnostics_health(store: Any = Depends(get_store)) -> dict:
    health = sanitize_diagnostics(store.health())
    health["status"] = "ok" if health.get("available") else "degraded"
    return health


class UIEvent(BaseModel):
    """No arbitrary messages, exception text, URLs, or metadata from the browser."""

    model_config = ConfigDict(extra="forbid", strict=True)
    event: Literal["ui_action", "ui_error", "ui_request_started", "ui_request_completed", "ui_request_failed", "ui_render_failed"]
    stage: Literal["ui", "navigation", "submission", "polling", "rendering"] = "ui"
    level: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    outcome: Literal["running", "queued", "success", "partial", "no_picks", "failed"] | None = None
    duration_ms: Annotated[int | None, Field(ge=0, le=86_400_000)] = None
    operation_id: CorrelationId
    request_id: CorrelationId | None = None
    component: Literal["picks", "slate", "best_today", "availability", "diagnostics", "navigation"] | None = None
    action: Literal["load", "submit", "refresh", "poll", "export", "cancel"] | None = None


@router.post("/ui-events", status_code=202)
def ingest_ui_event(payload: UIEvent) -> dict:
    values = payload.model_dump(exclude_none=True)
    event = values.pop("event")
    # Alias resolution keeps UI events attached to the actual operation.
    store = get_store()
    operation = _operation(store, values["operation_id"])
    values["operation_id"] = operation["operation_id"]
    values["service"] = "ui"
    values["origin"] = "untrusted_client"
    if not emit(event, **values):
        raise HTTPException(503, "The diagnostic event could not be recorded.")
    return {"accepted": True}


@admin_router.get("/operations/{operation_id}")
def technical_operation_detail(operation_id: OperationId, store: Any = Depends(get_store)) -> dict:
    operation = _operation(store, operation_id)
    events, completeness = _snapshot(store, operation, 100, technical=True)
    return {"operation": sanitize_diagnostics(operation, technical=True), "events": events, "completeness": completeness}


@admin_router.post("/operations/{operation_id}/debug")
def enable_debug(operation_id: OperationId, store: Any = Depends(get_store)) -> dict:
    _operation(store, operation_id)
    if not store.debug(operation_id, seconds=900):
        raise HTTPException(409, "Debug could not be enabled for this operation.")
    return {"operation_id": operation_id, "debug": True, "seconds": 900}
