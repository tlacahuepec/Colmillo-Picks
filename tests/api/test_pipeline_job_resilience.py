"""Tests for _execute_pipeline_job post-success resilience.

Ensures that failures in non-critical ledger operations do not crash the
background task or leave jobs stuck in 'running' state.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest

from services.api import db as db_module
from services.api import main as api_main


_TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'colmillo-test.db'}")


@pytest.fixture
def mock_pipeline(monkeypatch: pytest.MonkeyPatch):
    """Patches sport module pipeline to return a successful result."""
    fake_result = {
        "scores": [{"player": "Judge", "market": "hits", "line": 1.5, "score": 80}],
        "match_inputs": {"home_team": "NYY", "away_team": "CLE"},
        "steps": [{"name": "collect", "status": "ok", "duration_ms": 100}],
        "report_markdown": "# Report",
        "trace": {"run_id": "test"},
    }
    monkeypatch.setattr(api_main, "_run_sport_module_pipeline", lambda req: fake_result)
    return fake_result


def _create_job_and_dequeue(request_dict: dict[str, Any] | None = None) -> tuple[str, str]:
    """Create a pending pick, enqueue it, dequeue it, return (pick_id, job_id)."""
    req = request_dict or {"sport": "baseball", "_sport_module_path": True, "home_team": "NYY", "away_team": "CLE"}
    row = db_module.create_pending_pick_run(request_payload=req)
    from services.api import jobs as jobs_module

    jobs_module.enqueue_pick_run(pick_id=row.id, request_dict=req, bundle_kwargs={})
    item = jobs_module.dequeue_pick_run()
    assert item is not None
    return item[0], item[3]  # pick_id, job_id


class TestLedgerCrashResilience:
    """Post-success ledger failures must not crash the job."""

    def test_ledger_complete_run_crash_does_not_crash_job(self, mock_pipeline, monkeypatch):
        """If ledger.complete_run raises, job still returns True and pick is 'success'."""
        pick_id, _job_id = _create_job_and_dequeue()

        mock_ledger = MagicMock()
        mock_ledger.start_run.return_value = MagicMock(id="run-1")
        mock_ledger.complete_run.side_effect = RuntimeError("ledger DB locked")
        monkeypatch.setattr(api_main, "_build_run_ledger", lambda: mock_ledger)

        result = api_main._execute_pipeline_job(
            pick_id=pick_id,
            request_dict={"sport": "baseball", "_sport_module_path": True},
            bundle_kwargs={},
        )

        assert result is True
        row = db_module.get_pick_run(pick_id)
        assert row.status == "success"

    def test_ledger_record_step_crash_logged(self, mock_pipeline, monkeypatch, caplog):
        """If ledger.record_step raises, error is logged but job still succeeds."""
        pick_id, _job_id = _create_job_and_dequeue()

        mock_ledger = MagicMock()
        mock_ledger.start_run.return_value = MagicMock(id="run-1")
        mock_ledger.record_step.side_effect = RuntimeError("unexpected IO error")
        monkeypatch.setattr(api_main, "_build_run_ledger", lambda: mock_ledger)

        with caplog.at_level(logging.ERROR, logger="colmillo"):
            result = api_main._execute_pipeline_job(
                pick_id=pick_id,
                request_dict={"sport": "baseball", "_sport_module_path": True},
                bundle_kwargs={},
            )

        assert result is True
        assert "ledger_post_success_failed" in caplog.text or "unexpected IO error" in caplog.text

    def test_mark_pick_success_failure_returns_false(self, mock_pipeline, monkeypatch):
        """If mark_pick_success raises, job returns False (critical failure)."""
        pick_id, _job_id = _create_job_and_dequeue()

        mock_ledger = MagicMock()
        mock_ledger.start_run.return_value = MagicMock(id="run-1")
        monkeypatch.setattr(api_main, "_build_run_ledger", lambda: mock_ledger)
        monkeypatch.setattr(db_module, "mark_pick_success", _raise_runtime_error)

        result = api_main._execute_pipeline_job(
            pick_id=pick_id,
            request_dict={"sport": "baseball", "_sport_module_path": True},
            bundle_kwargs={},
        )

        assert result is False


def _raise_runtime_error(**kwargs):
    raise RuntimeError("DB write failed")
