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


_TEST_API_KEY = "test-api-key"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Authenticated test client.

    Sets ``COLMILLO_API_KEY`` and injects ``X-API-Key`` on every request so
    individual tests can focus on the handler behaviour, not on auth.
    """
    monkeypatch.delenv("API_FOOTBALL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("SOCCER_FIXTURE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("COLMILLO_UI_ORIGIN", raising=False)
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    test_client = TestClient(api_main.create_app())
    test_client.headers.update({"X-API-Key": _TEST_API_KEY})
    return test_client


@pytest.fixture
def unauthenticated_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Client without the default ``X-API-Key`` header for auth-focused tests."""
    monkeypatch.delenv("COLMILLO_UI_ORIGIN", raising=False)
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    return TestClient(api_main.create_app())


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
    monkeypatch.setenv("API_FOOTBALL_API_KEY", "x")

    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["providers"]["api_football"] is True
    assert body["providers"]["openai"] is False


def test_picks_returns_payload_and_report(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    captured = _patch_pipeline(monkeypatch)

    response = client.post(
        "/picks",
        json={
            "match_query": "juve - milan today",
            "top_n": 3,
            "league": "Serie A",
            "season": "2025",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["report_markdown"] == "# Mock report"
    assert body["scores"] == [{"player": "A"}]
    assert body["trace"] == {"llm_status": "not_requested"}
    assert body["match_inputs"] == {"match": {"id": "x"}}

    assert captured["bundle_kwargs"]["use_llm"] is False
    assert captured["bundle_kwargs"]["league"] == "Serie A"
    assert captured["bundle_kwargs"]["season"] == "2025"
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
        raise ValueError("Missing credentials for provider 'api-football'.")

    monkeypatch.setattr(api_main, "build_dependency_bundle", raising_bundle)

    response = client.post("/picks", json={"match_query": "juve - milan today"})

    assert response.status_code == 400
    assert "Missing credentials" in response.json()["detail"]


def test_picks_maps_collect_stage_to_400(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    err = api_main.PipelineServiceError(stage="collect")
    err.__cause__ = ValueError("Fixture lookup failed: no match found.")
    _patch_pipeline(monkeypatch, pipeline_error=err)

    response = client.post("/picks", json={"match_query": "juve - milan today"})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["stage"] == "collect"
    assert "Fixture lookup failed" in detail["message"]


def test_picks_maps_score_stage_to_502(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    err = api_main.PipelineServiceError(stage="score")
    err.__cause__ = RuntimeError("scoring blew up")
    _patch_pipeline(monkeypatch, pipeline_error=err)

    response = client.post("/picks", json={"match_query": "juve - milan today"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["stage"] == "score"
    assert "scoring blew up" in detail["message"]


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

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "fixed-req-id"

    request_records = [r for r in caplog.records if r.message == "request"]
    assert request_records, "expected a 'request' log record"
    record = request_records[-1]
    assert record.request_id == "fixed-req-id"
    assert record.method == "POST"
    assert record.path == "/picks"
    assert record.status_code == 200
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
