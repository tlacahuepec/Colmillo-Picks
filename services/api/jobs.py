from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from services.api import db


def enqueue_pick_run(pick_id: str, request_dict: dict[str, Any], bundle_kwargs: dict[str, Any]) -> None:
    db.enqueue_pick_job(pick_id=pick_id, request_dict=request_dict, bundle_kwargs=bundle_kwargs)


def dequeue_pick_run() -> tuple[str, dict[str, Any], dict[str, Any], str] | None:
    job = db.dequeue_pick_job()
    if job is None:
        return None
    request = json.loads(job.request_json)
    request.update(_job_metadata(job))
    return job.pick_id, request, json.loads(job.bundle_kwargs_json), job.id


def _job_metadata(job) -> dict[str, Any]:
    created = job.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {"job_id": job.id, "attempt": job.attempts,
            "queue_ms": max(0, round((datetime.now(timezone.utc) - created).total_seconds() * 1000))}


def mark_job_done(job_id: str) -> None:
    db.mark_job_finished(job_id=job_id, success=True)


def mark_job_failed(job_id: str, message: str) -> None:
    db.mark_job_finished(job_id=job_id, success=False, error_message=message)


# --------------------------------------------------------------------------- #
# Slate queue helpers (Issue #212)                                             #
# --------------------------------------------------------------------------- #


def enqueue_slate_run(slate_id: str, request_dict: dict[str, Any]) -> None:
    db.enqueue_slate_job(slate_id=slate_id, request_dict=request_dict)


def dequeue_slate_run() -> tuple[str, dict[str, Any], str] | None:
    job = db.dequeue_slate_job()
    if job is None:
        return None
    request = json.loads(job.request_json)
    request.update(_job_metadata(job))
    return job.slate_id, request, job.id


def mark_slate_job_done(job_id: str) -> None:
    db.mark_slate_job_finished(job_id=job_id, success=True)


def mark_slate_job_failed(job_id: str, message: str) -> None:
    db.mark_slate_job_finished(job_id=job_id, success=False, error_message=message)
