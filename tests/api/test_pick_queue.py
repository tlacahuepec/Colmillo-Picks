from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from services.api import db as db_module
from services.api import main as api_main

_TEST_API_KEY = "test-api-key"

@pytest.fixture(autouse=True)
def isolated_db(tmp_path) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'colmillo-test.db'}")

@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    test_client = TestClient(api_main.create_app())
    test_client.headers.update({"X-API-Key": _TEST_API_KEY})
    return test_client


def test_post_picks_enqueues_job(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(api_main, "build_dependency_bundle", lambda **_: {"deps": "bundle"})

    response = client.post("/picks", json={"match_query": "a - b today"})

    assert response.status_code == 202
    pick_id = response.json()["id"]
    assert response.json()["status"] == "queued"

    status = client.get(f"/picks/{pick_id}/status").json()
    assert status["status"] == "queued"


def test_status_transitions_running_success(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(api_main, "build_dependency_bundle", lambda **_: {"deps": "bundle"})

    response = client.post("/picks", json={"match_query": "a - b today"})
    pick_id = response.json()["id"]

    job = db_module.dequeue_pick_job()
    assert job is not None
    assert db_module.get_pick_run(pick_id).status == "running"

    monkeypatch.setattr(api_main, "run_pipeline_with_payload", lambda **_: {
        "report_markdown": "# ok",
        "scores": [{"player": "A"}],
        "trace": {"llm_status": "not_requested"},
        "match_inputs": {"match": {"id": "x"}},
    })
    monkeypatch.setattr(api_main, "build_dependency_bundle", lambda **_: {"deps": "bundle"})
    api_main._execute_pipeline_job(
        pick_id=pick_id,
        request_dict={"match_query": "a - b today", "top_n": 5, "competition": "League"},
        bundle_kwargs={},
    )

    status = client.get(f"/picks/{pick_id}/status").json()
    assert status["status"] == "success"
