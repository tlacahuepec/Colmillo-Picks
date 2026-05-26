"""Tests for POST /picks/{pick_id}/availability endpoint."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.api import main as api_main
from services.api import db as db_module


_TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'colmillo-avail-test.db'}")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("COLMILLO_UI_ORIGIN", raising=False)
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    monkeypatch.setenv("COLMILLO_RATE_LIMIT_PER_HOUR", "0")
    monkeypatch.setenv("COLMILLO_WORKER_MODE", "external")
    test_client = TestClient(api_main.create_app())
    test_client.headers.update({"X-API-Key": _TEST_API_KEY})
    return test_client


def _seed_pick(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> str:
    """Create a pick with known scores for availability testing."""

    def fake_build_bundle(**_: Any) -> dict[str, Any]:
        return {"deps": "bundle"}

    def fake_run_pipeline(*, request: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
        return {
            "report_markdown": "# Report",
            "scores": [
                {"player": "Aaron Judge", "player_id": "judge_1", "market": "hits", "line": 1.5, "direction": "over", "score": 0.72},
                {"player": "Mookie Betts", "player_id": "betts_1", "market": "strikeouts", "line": 1.5, "direction": "under", "score": 0.65},
            ],
            "trace": {"llm_status": "not_requested"},
            "match_inputs": {"match": {"id": "NYY-BOS"}},
        }

    monkeypatch.setattr(api_main, "build_dependency_bundle", fake_build_bundle)
    monkeypatch.setattr(api_main, "run_pipeline_with_payload", fake_run_pipeline)

    resp = client.post("/picks", json={"match_query": "NYY - BOS today"})
    pick_id = resp.json()["id"]
    from services.api import jobs as jobs_module
    item = jobs_module.dequeue_pick_run()
    if item:
        pick_id_j, req, bkw, _jid = item
        api_main._execute_pipeline_job(pick_id=pick_id_j, request_dict=req, bundle_kwargs=bkw)
    return pick_id


class TestAvailabilityEndpoint:
    def test_returns_badges_for_existing_pick(self, client, monkeypatch):
        pick_id = _seed_pick(client, monkeypatch)
        resp = client.post(f"/picks/{pick_id}/availability", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["pick_id"] == pick_id
        assert "badges" in body
        assert len(body["badges"]) >= 1
        assert "checked_at" in body

    def test_404_for_unknown_pick(self, client):
        resp = client.post("/picks/nonexistent-id/availability", json={})
        assert resp.status_code == 404

    def test_badges_have_required_fields(self, client, monkeypatch):
        pick_id = _seed_pick(client, monkeypatch)
        resp = client.post(f"/picks/{pick_id}/availability", json={})
        badge = resp.json()["badges"][0]
        assert "player" in badge
        assert "market" in badge
        assert "line" in badge
        assert "status" in badge
        assert "platform" in badge
        assert "last_checked" in badge

    def test_fallback_mode_on_adapter_error(self, client, monkeypatch):
        pick_id = _seed_pick(client, monkeypatch)
        monkeypatch.setattr(
            api_main, "_check_availability_for_picks",
            lambda picks, platforms: (_ for _ in ()).throw(RuntimeError("adapter down")),
        )
        resp = client.post(f"/picks/{pick_id}/availability", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert body["fallback_mode"] is True
        assert "adapter" in body["fallback_reason"].lower() or "error" in body["fallback_reason"].lower()

    def test_platform_filter_passed_to_adapter(self, client, monkeypatch):
        pick_id = _seed_pick(client, monkeypatch)
        resp = client.post(
            f"/picks/{pick_id}/availability",
            json={"platforms": ["prizepicks"]},
        )
        assert resp.status_code == 200
        for badge in resp.json()["badges"]:
            assert badge["platform"] in ("prizepicks", "mock")
