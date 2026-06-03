"""RED tests for slate persistence (SlateRun / SlateJob models and CRUD)."""

from __future__ import annotations

import json
import uuid

import pytest

from services.api import db as db_module
from services.api.db import (
    PICK_STATUS_FAILED,
    PICK_STATUS_PENDING,
    PICK_STATUS_QUEUED,
    PICK_STATUS_SUCCESS,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'slate-test.db'}")


def _sample_request() -> dict:
    return {
        "date": "2026-06-01",
        "sports": ["soccer", "basketball"],
        "max_matches_per_sport": 3,
        "top_n": 10,
    }


class TestCreatePendingSlateRun:
    def test_persists_request_with_pending_status(self) -> None:
        row = db_module.create_pending_slate_run(request_payload=_sample_request())

        assert row.id is not None
        assert row.status == PICK_STATUS_PENDING
        assert row.created_at is not None
        stored = json.loads(row.request_json)
        assert stored["date"] == "2026-06-01"
        assert stored["sports"] == ["soccer", "basketball"]

    def test_strips_sensitive_keys(self) -> None:
        payload = {**_sample_request(), "api_key": "secret", "authorization": "Bearer x"}
        row = db_module.create_pending_slate_run(request_payload=payload)

        stored = json.loads(row.request_json)
        assert "api_key" not in stored
        assert "authorization" not in stored


class TestEnqueueAndDequeueSlateJob:
    def test_fifo_ordering(self) -> None:
        row1 = db_module.create_pending_slate_run(request_payload=_sample_request())
        row2 = db_module.create_pending_slate_run(request_payload=_sample_request())
        db_module.enqueue_slate_job(slate_id=row1.id, request_dict=_sample_request())
        db_module.enqueue_slate_job(slate_id=row2.id, request_dict=_sample_request())

        first = db_module.dequeue_slate_job()
        assert first is not None
        assert first.slate_id == row1.id

        second = db_module.dequeue_slate_job()
        assert second is not None
        assert second.slate_id == row2.id

    def test_dequeue_returns_none_when_empty(self) -> None:
        result = db_module.dequeue_slate_job()
        assert result is None

    def test_enqueue_sets_slate_status_to_queued(self) -> None:
        row = db_module.create_pending_slate_run(request_payload=_sample_request())
        db_module.enqueue_slate_job(slate_id=row.id, request_dict=_sample_request())

        refreshed = db_module.get_slate_run(row.id)
        assert refreshed is not None
        assert refreshed.status == PICK_STATUS_QUEUED

    def test_dequeue_sets_status_to_running(self) -> None:
        row = db_module.create_pending_slate_run(request_payload=_sample_request())
        db_module.enqueue_slate_job(slate_id=row.id, request_dict=_sample_request())

        job = db_module.dequeue_slate_job()
        assert job is not None

        refreshed = db_module.get_slate_run(row.id)
        assert refreshed is not None
        assert refreshed.status == "running"


class TestMarkSlateSuccess:
    def test_stores_candidates_and_timing(self) -> None:
        row = db_module.create_pending_slate_run(request_payload=_sample_request())
        candidates = [{"player": "Saka", "normalized_score": 85.5}]
        match_runs = [{"sport": "soccer", "status": "success"}]

        db_module.mark_slate_success(
            slate_id=row.id,
            candidates=candidates,
            match_runs=match_runs,
            latency_ms=1200,
            discovery_latency_ms=400,
            matches_attempted=3,
            matches_succeeded=2,
        )

        refreshed = db_module.get_slate_run(row.id)
        assert refreshed is not None
        assert refreshed.status == PICK_STATUS_SUCCESS
        assert refreshed.latency_ms == 1200
        assert refreshed.discovery_latency_ms == 400
        assert refreshed.matches_attempted == 3
        assert refreshed.matches_succeeded == 2
        assert json.loads(refreshed.candidates_json) == candidates
        assert json.loads(refreshed.match_runs_json) == match_runs


class TestMarkSlateFailed:
    def test_stores_stage_and_message(self) -> None:
        row = db_module.create_pending_slate_run(request_payload=_sample_request())

        db_module.mark_slate_failed(
            slate_id=row.id,
            stage="discovery",
            message="LLM provider timeout",
            latency_ms=5000,
        )

        refreshed = db_module.get_slate_run(row.id)
        assert refreshed is not None
        assert refreshed.status == PICK_STATUS_FAILED
        assert refreshed.error_stage == "discovery"
        assert refreshed.error_message == "LLM provider timeout"
        assert refreshed.latency_ms == 5000


class TestGetSlateRun:
    def test_returns_none_for_unknown_id(self) -> None:
        result = db_module.get_slate_run(str(uuid.uuid4()))
        assert result is None


class TestListSlateRuns:
    def test_respects_limit_offset(self) -> None:
        for _ in range(5):
            db_module.create_pending_slate_run(request_payload=_sample_request())

        page1 = db_module.list_slate_runs(limit=2, offset=0)
        assert len(page1) == 2

        page2 = db_module.list_slate_runs(limit=2, offset=2)
        assert len(page2) == 2

        page3 = db_module.list_slate_runs(limit=2, offset=4)
        assert len(page3) == 1

    def test_orders_by_created_at_desc(self) -> None:
        for _ in range(3):
            db_module.create_pending_slate_run(request_payload=_sample_request())

        runs = db_module.list_slate_runs(limit=10, offset=0)
        dates = [r.created_at for r in runs]
        assert dates == sorted(dates, reverse=True)


class TestMarkSlateJobFinished:
    def test_marks_success(self) -> None:
        row = db_module.create_pending_slate_run(request_payload=_sample_request())
        db_module.enqueue_slate_job(slate_id=row.id, request_dict=_sample_request())
        job = db_module.dequeue_slate_job()
        assert job is not None

        db_module.mark_slate_job_finished(job_id=job.id, success=True)

    def test_marks_failure_with_error(self) -> None:
        row = db_module.create_pending_slate_run(request_payload=_sample_request())
        db_module.enqueue_slate_job(slate_id=row.id, request_dict=_sample_request())
        job = db_module.dequeue_slate_job()
        assert job is not None

        db_module.mark_slate_job_finished(
            job_id=job.id, success=False, error_message="pipeline crash"
        )
