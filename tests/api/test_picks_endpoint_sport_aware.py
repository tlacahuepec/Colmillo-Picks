"""Tests for sport-aware structured request support in POST /picks."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pipeline_runner import PipelineRunError
from services.api import main as api_main
from services.api import db as db_module


_TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'colmillo-test.db'}")
    monkeypatch.setenv("COLMILLO_RUNS_DB_PATH", str(tmp_path / "runs-ledger.db"))


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


class TestStructuredPicksRequest:
    def test_structured_soccer_request_returns_202(self, client: TestClient) -> None:
        resp = client.post("/picks", json={
            "sport": "soccer",
            "event_date": "2026-06-01",
            "home_team": "Arsenal",
            "away_team": "Liverpool",
            "markets": ["passes", "shots"],
            "top_n": 3,
            "allow_deterministic_fallback": True,
        })
        assert resp.status_code == 202
        data = resp.json()
        assert "id" in data
        assert data["status"] == "pending"

    def test_sport_module_pipeline_error_persists_stage(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        row = db_module.create_pending_pick_run(
            request_payload={
                "_sport_module_path": True,
                "sport": "baseball",
                "home_team": "CIN",
                "away_team": "ATL",
                "event_date": "2026-05-29",
                "markets": ["hits"],
                "top_n": 5,
                "league": "mlb",
            }
        )

        def fail_pipeline(_request_dict):
            raise PipelineRunError(
                stage="score",
                message="Could not find enough match details: missing prop lines.",
            )

        monkeypatch.setattr(api_main, "_run_sport_module_pipeline", fail_pipeline)

        api_main._execute_pipeline_job(
            pick_id=row.id,
            request_dict={
                "_sport_module_path": True,
                "sport": "baseball",
                "home_team": "CIN",
                "away_team": "ATL",
                "event_date": "2026-05-29",
                "markets": ["hits"],
                "top_n": 5,
                "league": "mlb",
            },
            bundle_kwargs={},
        )

        status = client.get(f"/picks/{row.id}/status").json()
        assert status["status"] == "failed"
        assert status["error_stage"] == "score"
        assert "Could not find enough match details" in status["error_message"]

    def test_invalid_sport_returns_400(self, client: TestClient) -> None:
        resp = client.post("/picks", json={
            "sport": "cricket",
            "event_date": "2026-06-01",
            "home_team": "Team A",
            "away_team": "Team B",
            "markets": ["runs"],
        })
        assert resp.status_code == 400
        assert "cricket" in resp.json()["detail"]

    def test_invalid_market_for_sport_returns_400(self, client: TestClient) -> None:
        resp = client.post("/picks", json={
            "sport": "basketball",
            "event_date": "2026-06-01",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "markets": ["passes"],
        })
        assert resp.status_code == 400
        assert "passes" in resp.json()["detail"]

    def test_basketball_sport_returns_202_accepted(self, client: TestClient) -> None:
        resp = client.post("/picks", json={
            "sport": "basketball",
            "event_date": "2026-06-01",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "markets": ["points", "rebounds"],
        })
        assert resp.status_code == 202
        data = resp.json()
        assert "id" in data
        assert data["status"] == "pending"


class TestLegacyPicksRequestRegression:
    def test_match_query_request_still_works(self, client: TestClient) -> None:
        resp = client.post("/picks", json={
            "match_query": "arsenal - liverpool 2026-06-01",
            "top_n": 3,
            "allow_deterministic_fallback": True,
        })
        assert resp.status_code == 202
        data = resp.json()
        assert "id" in data
        assert data["status"] == "pending"
