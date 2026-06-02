"""Acceptance tests for baseball (MLB) requests via the API."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.api import main as api_main
from services.api import db as db_module


_TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'colmillo-test.db'}")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
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


def _run_next_job() -> None:
    item = api_main.jobs_module.dequeue_pick_run()
    assert item is not None
    pick_id, request_dict, bundle_kwargs, _job_id = item
    api_main._execute_pipeline_job(
        pick_id=pick_id,
        request_dict=request_dict,
        bundle_kwargs=bundle_kwargs,
    )


class TestBaseballAPIAcceptance:
    def test_baseball_request_accepted(self, client: TestClient) -> None:
        response = client.post(
            "/picks",
            json={
                "sport": "baseball",
                "home_team": "Yankees",
                "away_team": "Red Sox",
                "event_date": "2026-06-15",
                "league": "mlb",
            },
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "pending"
        assert "id" in body

    def test_baseball_request_fails_without_enough_match_details(self, client: TestClient) -> None:
        response = client.post(
            "/picks",
            json={
                "sport": "baseball",
                "home_team": "Yankees",
                "away_team": "Red Sox",
                "event_date": "2026-06-15",
                "league": "mlb",
            },
        )
        assert response.status_code == 202
        pick_id = response.json()["id"]
        _run_next_job()

        detail = client.get(f"/picks/{pick_id}").json()
        assert detail["status"] == "failed"
        assert detail["error_stage"] == "collect"
        assert "Could not find enough match details" in detail["error_message"]
        assert detail["scores"] == []

    def test_baseball_with_specific_markets_fails_without_enough_match_details(
        self, client: TestClient
    ) -> None:
        response = client.post(
            "/picks",
            json={
                "sport": "baseball",
                "home_team": "Yankees",
                "away_team": "Red Sox",
                "event_date": "2026-06-15",
                "league": "mlb",
                "markets": ["hits", "strikeouts"],
            },
        )
        assert response.status_code == 202
        pick_id = response.json()["id"]
        _run_next_job()

        detail = client.get(f"/picks/{pick_id}").json()
        assert detail["status"] == "failed"
        assert detail["error_stage"] == "collect"
        assert "Could not find enough match details" in detail["error_message"]
        assert detail["scores"] == []

    def test_baseball_npb_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/picks",
            json={
                "sport": "baseball",
                "home_team": "Giants",
                "away_team": "Tigers",
                "event_date": "2026-06-15",
                "league": "npb",
            },
        )
        assert response.status_code == 400

    def test_baseball_kbo_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/picks",
            json={
                "sport": "baseball",
                "home_team": "Lions",
                "away_team": "Bears",
                "event_date": "2026-06-15",
                "league": "kbo",
            },
        )
        assert response.status_code == 400

    def test_api_never_returns_zero_line_picks_in_scores(
        self, monkeypatch: pytest.MonkeyPatch, client: TestClient
    ) -> None:
        def fake_sport_pipeline(request_dict: dict[str, Any]) -> dict[str, Any]:
            return {
                "scores": [
                    {"player": "BadPick", "market": "hits", "line": 0, "score": 0.5},
                    {"player": "GoodPick", "market": "hits", "line": 1.5, "score": 0.8},
                ],
                "match_inputs": {"home_team": "NYY", "away_team": "BOS"},
                "steps": [{"name": "collect", "status": "success", "duration_ms": 10}],
                "report_markdown": "# Report",
                "trace": {"llm_status": "not_requested"},
            }

        monkeypatch.setattr(api_main, "_run_sport_module_pipeline", fake_sport_pipeline)

        response = client.post(
            "/picks",
            json={
                "sport": "baseball",
                "home_team": "Yankees",
                "away_team": "Red Sox",
                "event_date": "2026-06-15",
                "league": "mlb",
            },
        )
        assert response.status_code == 202
        pick_id = response.json()["id"]
        _run_next_job()

        detail = client.get(f"/picks/{pick_id}").json()
        assert detail["status"] == "success"
        for score in detail["scores"]:
            assert score.get("line") != 0, f"Zero-line pick leaked to API: {score}"

    def test_soccer_still_works(
        self, monkeypatch: pytest.MonkeyPatch, client: TestClient
    ) -> None:
        def fake_build_bundle(**kwargs: Any) -> dict:
            return {"deps": "bundle"}

        def fake_run_pipeline(*, request: dict, deps: dict) -> dict:
            return {
                "report_markdown": "# Mock",
                "scores": [{"player": "Test", "market": "passes"}],
                "trace": {"llm_status": "not_requested"},
                "match_inputs": {"match": {"id": "x"}},
            }

        monkeypatch.setattr(api_main, "build_dependency_bundle", fake_build_bundle)
        monkeypatch.setattr(api_main, "run_pipeline_with_payload", fake_run_pipeline)

        response = client.post(
            "/picks",
            json={"match_query": "bayern - stuttgart today"},
        )
        assert response.status_code == 202
        pick_id = response.json()["id"]
        _run_next_job()

        detail = client.get(f"/picks/{pick_id}").json()
        assert detail["status"] == "success"

    def test_basketball_still_works(self, client: TestClient) -> None:
        response = client.post(
            "/picks",
            json={
                "sport": "basketball",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "event_date": "2026-06-01",
            },
        )
        assert response.status_code == 202
        pick_id = response.json()["id"]
        _run_next_job()

        detail = client.get(f"/picks/{pick_id}").json()
        assert detail["status"] == "success"
