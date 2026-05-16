from __future__ import annotations

import json
from typing import Any

from services.api import db


def enqueue_pick_run(pick_id: str, request_dict: dict[str, Any], bundle_kwargs: dict[str, Any]) -> None:
    db.enqueue_pick_job(pick_id=pick_id, request_dict=request_dict, bundle_kwargs=bundle_kwargs)


def dequeue_pick_run() -> tuple[str, dict[str, Any], dict[str, Any], str] | None:
    job = db.dequeue_pick_job()
    if job is None:
        return None
    return job.pick_id, json.loads(job.request_json), json.loads(job.bundle_kwargs_json), job.id


def mark_job_done(job_id: str) -> None:
    db.mark_job_finished(job_id=job_id, success=True)


def mark_job_failed(job_id: str, message: str) -> None:
    db.mark_job_finished(job_id=job_id, success=False, error_message=message)
