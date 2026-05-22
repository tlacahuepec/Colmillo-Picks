"""Tests for the FastAPI wrapper around the pick pipeline.

The handler delegates to ``pipeline_service.run_pipeline_with_payload``; tests
patch that seam (and ``build_dependency_bundle``) so we don't hit any external
provider during unit tests.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.api import main as api_main
from services.api import db as db_module


_TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path) -> None:
    """Use a per-test SQLite file so persistence tests don't share state."""
    db_module.configure_engine(f"sqlite:///{tmp_path / 'colmillo-test.db'}")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Authenticated test client.

    Sets ``COLMILLO_API_KEY`` and injects ``X-API-Key`` on every request so
    individual tests can focus on the handler behaviour, not on auth.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("SOCCER_FIXTURE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("COLMILLO_UI_ORIGIN", raising=False)
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    monkeypatch.setenv("COLMILLO_WORKER_MODE", "external")
    test_client = TestClient(api_main.create_app())
    test_client.headers.update({"X-API-Key": _TEST_API_KEY})
    return test_client


@pytest.fixture
def unauthenticated_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Client without the default ``X-API-Key`` header for auth-focused tests."""
    monkeypatch.delenv("COLMILLO_UI_ORIGIN", raising=False)
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    return TestClient(api_main.create_app())



def _run_next_job() -> None:
    item = api_main.jobs_module.dequeue_pick_run()
    assert item is not None
    pick_id, request_dict, bundle_kwargs, _job_id = item
    api_main._execute_pipeline_job(
        pick_id=pick_id,
        request_dict=request_dict,
        bundle_kwargs=bundle_kwargs,
    )


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    bundle_factory=None,
    pipeline_result: dict[str, Any] | None = None,
    pipeline_error: Exception | None = None,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_build_bundle(**kwargs: Any) -> dict[str, Any]:
        captured["bundle_kwargs"] = kwargs
        if bundle_factory is not None:
            return bundle_factory(**kwargs)
        return {"deps": "bundle"}

    def fake_run_pipeline(*, request: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
        captured["request"] = request
        captured["deps"] = deps
        if pipeline_error is not None:
            raise pipeline_error
        return pipeline_result or {
            "report_markdown": "# Mock report",
            "scores": [{"player": "A"}],
            "trace": {"llm_status": "not_requested"},
            "match_inputs": {"match": {"id": "x"}},
        }

    monkeypatch.setattr(api_main, "build_dependency_bundle", fake_build_bundle)
    monkeypatch.setattr(api_main, "run_pipeline_with_payload", fake_run_pipeline)
    return captured


def test_healthz_reports_provider_status(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "x")

    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["providers"]["gemini"] is True
    assert body["providers"]["openai"] is False


def test_picks_returns_payload_and_report(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    captured = _patch_pipeline(monkeypatch)

    response = client.post(
        "/picks",
        json={
            "match_query": "juve - milan today",
            "top_n": 3,
            "league": "Serie A",
        },
    )

    # POST is queue-backed: returns 202 and worker processes later.
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "pending"
    pick_id = accepted["id"]
    _run_next_job()

    detail = client.get(f"/picks/{pick_id}").json()
    assert detail["status"] == "success"
    assert detail["report_markdown"] == "# Mock report"
    assert detail["scores"] == [{"player": "A"}]
    assert detail["trace"] == {"llm_status": "not_requested"}

    assert captured["bundle_kwargs"]["use_llm"] is False
    assert captured["bundle_kwargs"]["league"] == "Serie A"
    assert captured["request"]["match_query"] == "juve - milan today"
    assert captured["request"]["top_n"] == 3
    assert captured["request"]["competition"] == "Serie A"


def test_picks_rejects_use_llm_without_provider(client: TestClient) -> None:
    response = client.post(
        "/picks",
        json={"match_query": "juve - milan today", "use_llm": True},
    )

    assert response.status_code == 400
    assert "llm_provider" in response.json()["detail"]


def test_picks_validates_top_n_bounds(client: TestClient) -> None:
    response = client.post(
        "/picks",
        json={"match_query": "juve - milan today", "top_n": 99},
    )

    assert response.status_code == 422


def test_picks_returns_400_when_dependency_bundle_rejects_inputs(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    def raising_bundle(**_: Any) -> dict[str, Any]:
        raise ValueError("Missing credentials for LLM fixture provider.")

    monkeypatch.setattr(api_main, "build_dependency_bundle", raising_bundle)

    response = client.post("/picks", json={"match_query": "juve - milan today"})

    assert response.status_code == 400
    assert "Missing credentials" in response.json()["detail"]


def test_picks_records_collect_failure_via_status(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    err = api_main.PipelineServiceError(stage="collect")
    err.__cause__ = ValueError("Fixture lookup failed: no match found.")
    _patch_pipeline(monkeypatch, pipeline_error=err)

    response = client.post("/picks", json={"match_query": "juve - milan today"})

    assert response.status_code == 202
    pick_id = response.json()["id"]

    _run_next_job()
    status = client.get(f"/picks/{pick_id}/status").json()
    assert status["status"] == "failed"
    assert status["error_stage"] == "collect"
    assert "Fixture lookup failed" in status["error_message"]


def test_picks_records_score_failure_via_status(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    err = api_main.PipelineServiceError(stage="score")
    err.__cause__ = RuntimeError("scoring blew up")
    _patch_pipeline(monkeypatch, pipeline_error=err)

    response = client.post("/picks", json={"match_query": "juve - milan today"})

    assert response.status_code == 202
    pick_id = response.json()["id"]

    _run_next_job()
    status = client.get(f"/picks/{pick_id}/status").json()
    assert status["status"] == "failed"
    assert status["error_stage"] == "score"
    assert "scoring blew up" in status["error_message"]


# --------------------------------------------------------------------------- #
# Auth, CORS, and structured logging                                          #
# --------------------------------------------------------------------------- #


def test_picks_requires_api_key(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/picks", json={"match_query": "juve - milan today"}
    )

    assert response.status_code == 401
    assert "X-API-Key" in response.json()["detail"]


def test_picks_rejects_wrong_api_key(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.post(
        "/picks",
        json={"match_query": "juve - milan today"},
        headers={"X-API-Key": "wrong"},
    )

    assert response.status_code == 401


def test_healthz_skips_auth(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_service_returns_503_when_api_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COLMILLO_API_KEY", raising=False)
    monkeypatch.delenv("COLMILLO_UI_ORIGIN", raising=False)
    test_client = TestClient(api_main.create_app())

    response = test_client.post(
        "/picks",
        json={"match_query": "juve - milan today"},
        headers={"X-API-Key": "anything"},
    )

    assert response.status_code == 503
    assert "COLMILLO_API_KEY" in response.json()["detail"]


def test_cors_allows_configured_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    monkeypatch.setenv("COLMILLO_UI_ORIGIN", "https://ui.example.test")
    test_client = TestClient(api_main.create_app())

    response = test_client.options(
        "/picks",
        headers={
            "Origin": "https://ui.example.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-API-Key, Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://ui.example.test"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_cors_blocks_unconfigured_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    monkeypatch.setenv("COLMILLO_UI_ORIGIN", "https://ui.example.test")
    test_client = TestClient(api_main.create_app())

    response = test_client.options(
        "/picks",
        headers={
            "Origin": "https://evil.example.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )

    # Starlette's CORS middleware returns 400 for disallowed origins on preflight.
    assert response.status_code == 400
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers.keys()}


def test_request_logging_emits_json_line(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _patch_pipeline(monkeypatch)

    with caplog.at_level(logging.INFO, logger="colmillo"):
        response = client.post(
            "/picks",
            json={"match_query": "juve - milan today"},
            headers={"X-Request-Id": "fixed-req-id"},
        )

    assert response.status_code == 202
    assert response.headers["X-Request-Id"] == "fixed-req-id"

    request_records = [r for r in caplog.records if r.message == "request"]
    assert request_records, "expected a 'request' log record"
    record = request_records[-1]
    assert record.request_id == "fixed-req-id"
    assert record.method == "POST"
    assert record.path == "/picks"
    assert record.status_code == 202
    assert isinstance(record.latency_ms, int) and record.latency_ms >= 0


def test_json_formatter_serializes_request_fields() -> None:
    from services.api.logging_config import JsonFormatter

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="colmillo",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request",
        args=(),
        exc_info=None,
    )
    record.request_id = "abc"
    record.method = "GET"
    record.path = "/healthz"
    record.status_code = 200
    record.latency_ms = 4

    payload = json.loads(formatter.format(record))

    assert payload["message"] == "request"
    assert payload["level"] == "INFO"
    assert payload["request_id"] == "abc"
    assert payload["method"] == "GET"
    assert payload["status_code"] == 200
    assert payload["latency_ms"] == 4


# --------------------------------------------------------------------------- #
# Persistence: POST /picks writes a row, GET /picks lists, GET /picks/{id}    #
# --------------------------------------------------------------------------- #


def test_picks_post_persists_row_and_returns_id(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    _patch_pipeline(
        monkeypatch,
        pipeline_result={
            "report_markdown": "# Stored report",
            "scores": [{"player": "A", "rank": 1}],
            "trace": {"llm_status": "not_requested", "notes": ["ok"]},
            "match_inputs": {"match": {"id": "EPL-1", "fixture_status": "scheduled"}},
        },
    )

    response = client.post(
        "/picks",
        json={"match_query": "juve - milan today", "league": "Serie A", "top_n": 4},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["id"]
    assert body["created_at"]
    assert body["status"] == "pending"

    _run_next_job()
    rows = db_module.list_pick_runs(limit=10, offset=0)
    assert len(rows) == 1
    stored = rows[0]
    assert stored.id == body["id"]
    assert stored.status == "success"
    assert stored.match_query == "juve - milan today"
    assert stored.competition == "Serie A"
    assert stored.top_n == 4
    assert stored.report_markdown == "# Stored report"
    assert json.loads(stored.scores_json) == [{"player": "A", "rank": 1}]
    assert json.loads(stored.trace_json)["llm_status"] == "not_requested"
    assert stored.fixture_status == "scheduled"
    assert stored.llm_status == "not_requested"
    assert stored.latency_ms is not None and stored.latency_ms >= 0


def test_picks_post_persists_failed_row_with_error_metadata(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    err = api_main.PipelineServiceError(stage="collect")
    err.__cause__ = ValueError("missing fixture")
    _patch_pipeline(monkeypatch, pipeline_error=err)

    response = client.post("/picks", json={"match_query": "juve - milan today"})

    assert response.status_code == 202
    _run_next_job()
    rows = db_module.list_pick_runs(limit=10, offset=0)
    assert len(rows) == 1
    stored = rows[0]
    assert stored.status == "failed"
    assert stored.error_stage == "collect"
    assert "missing fixture" in (stored.error_message or "")


def test_list_picks_paginates_in_reverse_chronological_order(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    _patch_pipeline(monkeypatch)

    ids: list[str] = []
    for label in ("first", "second", "third"):
        response = client.post(
            "/picks",
            json={"match_query": f"juve - milan today {label}", "league": label},
        )
        assert response.status_code == 202
        ids.append(response.json()["id"])

    response = client.get("/picks", params={"limit": 2, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == [ids[2], ids[1]]
    assert body["items"][0]["competition"] == "third"

    response = client.get("/picks", params={"limit": 2, "offset": 2})
    assert response.status_code == 200
    page = response.json()
    assert [item["id"] for item in page["items"]] == [ids[0]]


def test_list_picks_rejects_out_of_range_limit(client: TestClient) -> None:
    response = client.get("/picks", params={"limit": 0})

    assert response.status_code == 422


def test_get_pick_by_id_returns_full_payload(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    _patch_pipeline(monkeypatch)

    created = client.post("/picks", json={"match_query": "juve - milan today"})
    pick_id = created.json()["id"]

    _run_next_job()
    response = client.get(f"/picks/{pick_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == pick_id
    assert body["report_markdown"] == "# Mock report"
    assert body["scores"] == [{"player": "A"}]
    assert body["trace"] == {"llm_status": "not_requested"}
    # Persisted request must not include any auth-related secret keys.
    assert "x_api_key" not in {k.lower() for k in body["request"].keys()}


def test_get_pick_returns_404_for_unknown_id(client: TestClient) -> None:
    response = client.get("/picks/does-not-exist")

    assert response.status_code == 404


def test_create_pending_pick_strips_sensitive_request_keys() -> None:
    row = db_module.create_pending_pick_run(
        request_payload={
            "match_query": "x - y today",
            "top_n": 5,
            "league": "L",
            "X_API_KEY": "should-not-persist",
            "authorization": "Bearer secret",
        },
    )

    persisted = json.loads(row.request_json)
    keys_lower = {k.lower() for k in persisted.keys()}
    assert "x_api_key" not in keys_lower
    assert "authorization" not in keys_lower
    assert persisted["match_query"] == "x - y today"
    assert row.status == "pending"
