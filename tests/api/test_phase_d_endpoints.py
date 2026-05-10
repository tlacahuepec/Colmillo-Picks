"""Tests for the new async-status, outcomes, hit-rate, admin, and rate-limit
endpoints introduced in Phase D (Stories 8-10).

These live alongside ``test_picks_endpoint.py`` but are kept in a separate
module so the original Phase B suite stays focused on the sync persistence
contract.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.api import db as db_module
from services.api import main as api_main


_TEST_API_KEY = "phase-d-key"
_ADMIN_API_KEY = "phase-d-admin"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'colmillo-phaseD.db'}")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for var in (
        "API_FOOTBALL_API_KEY",
        "OPENAI_API_KEY",
        "XAI_API_KEY",
        "GROK_API_KEY",
        "SOCCER_FIXTURE_LLM_API_KEY",
        "COLMILLO_UI_ORIGIN",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    monkeypatch.setenv("COLMILLO_ADMIN_API_KEY", _ADMIN_API_KEY)
    # Disable rate-limiting by default; specific tests opt back in.
    monkeypatch.setenv("COLMILLO_RATE_LIMIT_PER_HOUR", "0")

    test_client = TestClient(api_main.create_app())
    test_client.headers.update({"X-API-Key": _TEST_API_KEY})
    return test_client


def _patch_default_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_build_bundle(**_: Any) -> dict[str, Any]:
        return {"deps": "bundle"}

    def fake_run_pipeline(*, request: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
        return {
            "report_markdown": f"# Report for {request['match_query']}",
            "scores": [{"player": "A", "rank": 1}],
            "trace": {"llm_status": "not_requested"},
            "match_inputs": {"match": {"id": "X"}},
        }

    monkeypatch.setattr(api_main, "build_dependency_bundle", fake_build_bundle)
    monkeypatch.setattr(api_main, "run_pipeline_with_payload", fake_run_pipeline)


# --------------------------------------------------------------------------- #
# Status endpoint                                                             #
# --------------------------------------------------------------------------- #


def test_pick_status_endpoint_reports_success(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    _patch_default_pipeline(monkeypatch)

    accepted = client.post("/picks", json={"match_query": "x - y today"}).json()
    response = client.get(f"/picks/{accepted['id']}/status")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == accepted["id"]
    assert body["status"] == "success"
    assert body["error_stage"] is None
    assert body["error_message"] is None
    assert isinstance(body["latency_ms"], int)


def test_pick_status_endpoint_reports_failure(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    err = api_main.PipelineServiceError(stage="score")
    err.__cause__ = RuntimeError("nope")

    def fake_build_bundle(**_: Any) -> dict[str, Any]:
        return {"deps": "bundle"}

    def fake_run_pipeline(**_: Any) -> dict[str, Any]:
        raise err

    monkeypatch.setattr(api_main, "build_dependency_bundle", fake_build_bundle)
    monkeypatch.setattr(api_main, "run_pipeline_with_payload", fake_run_pipeline)

    accepted = client.post("/picks", json={"match_query": "x - y today"}).json()
    body = client.get(f"/picks/{accepted['id']}/status").json()

    assert body["status"] == "failed"
    assert body["error_stage"] == "score"
    assert "nope" in body["error_message"]


def test_pick_status_returns_404_for_unknown_id(client: TestClient) -> None:
    response = client.get("/picks/missing/status")

    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Outcomes (Story 9)                                                          #
# --------------------------------------------------------------------------- #


def _create_successful_pick(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> str:
    _patch_default_pipeline(monkeypatch)
    return client.post("/picks", json={"match_query": "x - y today"}).json()["id"]


def test_post_outcomes_persists_and_returns_rows(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    pick_id = _create_successful_pick(monkeypatch, client)

    response = client.post(
        f"/picks/{pick_id}/outcomes",
        json={
            "outcomes": [
                {"rank": 1, "player": "Saka", "market": "shots", "result": "win"},
                {"rank": 2, "player": "Odegaard", "market": "passes", "result": "loss"},
            ]
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["pick_id"] == pick_id
    assert len(body["items"]) == 2
    assert {item["result"] for item in body["items"]} == {"win", "loss"}


def test_post_outcomes_rejects_invalid_result(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    pick_id = _create_successful_pick(monkeypatch, client)

    response = client.post(
        f"/picks/{pick_id}/outcomes",
        json={"outcomes": [{"rank": 1, "player": "Saka", "market": "shots", "result": "maybe"}]},
    )

    assert response.status_code == 422


def test_post_outcomes_returns_404_for_unknown_pick(client: TestClient) -> None:
    response = client.post(
        "/picks/missing/outcomes",
        json={"outcomes": [{"rank": 1, "player": "Saka", "market": "shots", "result": "win"}]},
    )

    assert response.status_code == 404


def test_get_outcomes_returns_persisted_rows(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    pick_id = _create_successful_pick(monkeypatch, client)
    client.post(
        f"/picks/{pick_id}/outcomes",
        json={"outcomes": [
            {"rank": 1, "player": "Saka", "market": "shots", "result": "win"}
        ]},
    )

    body = client.get(f"/picks/{pick_id}/outcomes").json()

    assert body["pick_id"] == pick_id
    assert len(body["items"]) == 1
    assert body["items"][0]["player"] == "Saka"


def test_hit_rate_aggregates_outcomes(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    pick_id = _create_successful_pick(monkeypatch, client)
    client.post(
        f"/picks/{pick_id}/outcomes",
        json={"outcomes": [
            {"rank": 1, "player": "A", "market": "shots", "result": "win"},
            {"rank": 2, "player": "B", "market": "passes", "result": "win"},
            {"rank": 3, "player": "C", "market": "tackles", "result": "loss"},
            {"rank": 4, "player": "D", "market": "shots", "result": "push"},
            {"rank": 5, "player": "E", "market": "shots", "result": "void"},
        ]},
    )

    body = client.get("/stats/hit-rate").json()

    assert body["totals"]["win"] == 2
    assert body["totals"]["loss"] == 1
    assert body["decided"] == 3
    assert body["hit_rate"] == pytest.approx(2 / 3)


def test_hit_rate_with_no_outcomes_returns_null_rate(client: TestClient) -> None:
    body = client.get("/stats/hit-rate").json()

    assert body["decided"] == 0
    assert body["hit_rate"] is None


# --------------------------------------------------------------------------- #
# Admin stats (Story 10)                                                      #
# --------------------------------------------------------------------------- #


def test_admin_stats_requires_admin_header(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    _patch_default_pipeline(monkeypatch)
    client.post("/picks", json={"match_query": "x - y today"})

    response = client.get("/admin/stats")

    assert response.status_code == 403


def test_admin_stats_returns_aggregates_when_authorized(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    _patch_default_pipeline(monkeypatch)
    pick_id = client.post("/picks", json={"match_query": "x - y today"}).json()["id"]
    client.post(
        f"/picks/{pick_id}/outcomes",
        json={"outcomes": [{"rank": 1, "player": "A", "market": "shots", "result": "win"}]},
    )

    response = client.get("/admin/stats", headers={"X-Admin-API-Key": _ADMIN_API_KEY})

    assert response.status_code == 200
    body = response.json()
    assert body["total_runs"] == 1
    assert body["by_status"].get("success") == 1
    assert body["outcomes_recorded"] == 1
    assert body["recent_failures"] == []


def test_admin_stats_returns_503_when_admin_key_unset(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.delenv("COLMILLO_ADMIN_API_KEY", raising=False)
    # Rebuild a fresh app so the middleware re-reads env state.
    fresh = TestClient(api_main.create_app())
    fresh.headers.update({"X-API-Key": _TEST_API_KEY})

    response = fresh.get("/admin/stats", headers={"X-Admin-API-Key": "anything"})

    assert response.status_code == 503


# --------------------------------------------------------------------------- #
# Rate limiting (Story 10)                                                    #
# --------------------------------------------------------------------------- #


def test_rate_limit_returns_429_when_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for var in ("API_FOOTBALL_API_KEY", "OPENAI_API_KEY", "COLMILLO_UI_ORIGIN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    monkeypatch.setenv("COLMILLO_RATE_LIMIT_PER_HOUR", "2")

    test_client = TestClient(api_main.create_app())
    test_client.headers.update({"X-API-Key": _TEST_API_KEY})

    # The first two requests succeed, the third must be throttled.
    assert test_client.get("/picks").status_code == 200
    assert test_client.get("/picks").status_code == 200

    response = test_client.get("/picks")

    assert response.status_code == 429
    assert response.headers.get("Retry-After")
    assert "Rate limit" in response.json()["detail"]


def test_rate_limit_does_not_apply_to_healthz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    monkeypatch.setenv("COLMILLO_RATE_LIMIT_PER_HOUR", "1")
    monkeypatch.delenv("COLMILLO_UI_ORIGIN", raising=False)

    test_client = TestClient(api_main.create_app())

    # Healthz is exempt from auth and the limiter; should always be 200.
    for _ in range(5):
        assert test_client.get("/healthz").status_code == 200


# --------------------------------------------------------------------------- #
# Sentry integration                                                          #
# --------------------------------------------------------------------------- #


def test_init_sentry_skipped_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    from services.api.sentry import init_sentry_if_configured

    monkeypatch.delenv("SENTRY_DSN", raising=False)

    assert init_sentry_if_configured() is False
