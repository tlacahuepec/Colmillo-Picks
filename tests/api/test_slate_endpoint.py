"""RED tests for the /slates API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.api import db as db_module
from services.api import main as api_main


_TEST_API_KEY = "slate-test-key"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'slate-endpoint.db'}")
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


class TestPostSlates:
    def test_returns_202_accepted(self, client: TestClient) -> None:
        response = client.post(
            "/slates",
            json={
                "date": "2026-06-01",
                "sports": ["soccer"],
                "max_matches_per_sport": 3,
                "top_n": 10,
            },
        )

        assert response.status_code == 202
        body = response.json()
        assert "id" in body
        assert body["status"] == "pending"
        assert "created_at" in body

    def test_validates_date_format(self, client: TestClient) -> None:
        response = client.post(
            "/slates",
            json={
                "date": "not-a-date",
                "sports": ["soccer"],
                "max_matches_per_sport": 3,
                "top_n": 10,
            },
        )

        assert response.status_code == 422

    def test_rejects_unsupported_sport(self, client: TestClient) -> None:
        response = client.post(
            "/slates",
            json={
                "date": "2026-06-01",
                "sports": ["cricket"],
                "max_matches_per_sport": 3,
                "top_n": 10,
            },
        )

        assert response.status_code in (400, 422)

    def test_validates_max_matches_per_sport_bounds(self, client: TestClient) -> None:
        response = client.post(
            "/slates",
            json={
                "date": "2026-06-01",
                "sports": ["soccer"],
                "max_matches_per_sport": 6,
                "top_n": 10,
            },
        )

        assert response.status_code == 422


class TestGetSlate:
    def test_returns_404_for_unknown_id(self, client: TestClient) -> None:
        response = client.get("/slates/nonexistent-id")
        assert response.status_code == 404

    def test_returns_pending_status_after_post(self, client: TestClient) -> None:
        post_resp = client.post(
            "/slates",
            json={
                "date": "2026-06-01",
                "sports": ["soccer"],
                "max_matches_per_sport": 3,
                "top_n": 10,
            },
        )
        slate_id = post_resp.json()["id"]

        status_resp = client.get(f"/slates/{slate_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] in ("pending", "queued")


class TestSlateFullSuccess:
    def test_returns_ranked_candidates(self, client: TestClient) -> None:
        row = db_module.create_pending_slate_run(
            request_payload={"date": "2026-06-01", "sports": ["soccer"], "max_matches_per_sport": 3, "top_n": 5}
        )
        candidates = [
            {
                "rank": 1,
                "sport": "soccer",
                "player": "Saka",
                "market": "passes",
                "line": 50.5,
                "direction": "over",
                "confidence": "high",
                "normalized_score": 90.0,
                "risk_flags": [],
                "availability_status": "unknown",
                "source_match": {"home_team": "Arsenal", "away_team": "Liverpool"},
            }
        ]
        match_runs = [{"sport": "soccer", "home_team": "Arsenal", "away_team": "Liverpool", "status": "success", "pick_count": 1}]
        db_module.mark_slate_success(
            slate_id=row.id,
            candidates=candidates,
            match_runs=match_runs,
            latency_ms=2000,
            discovery_latency_ms=500,
            matches_attempted=1,
            matches_succeeded=1,
        )

        response = client.get(f"/slates/{row.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert len(body["candidates"]) == 1
        assert body["candidates"][0]["player"] == "Saka"
        assert body["matches_attempted"] == 1
        assert body["matches_succeeded"] == 1
        assert body["latency_ms"] == 2000
        assert body["discovery_latency_ms"] == 500


class TestSlatePartialFailure:
    def test_still_succeeds(self, client: TestClient) -> None:
        row = db_module.create_pending_slate_run(
            request_payload={"date": "2026-06-01", "sports": ["soccer"], "max_matches_per_sport": 3, "top_n": 5}
        )
        candidates = [
            {
                "rank": 1,
                "sport": "soccer",
                "player": "Saka",
                "market": "passes",
                "line": 50.5,
                "direction": "over",
                "confidence": "high",
                "normalized_score": 85.0,
                "risk_flags": [],
                "availability_status": "unknown",
                "source_match": {"home_team": "Arsenal", "away_team": "Liverpool"},
            }
        ]
        match_runs = [
            {"sport": "soccer", "home_team": "Arsenal", "away_team": "Liverpool", "status": "success", "pick_count": 1},
            {"sport": "soccer", "home_team": "Barcelona", "away_team": "Real Madrid", "status": "failed", "error_stage": "pipeline", "error_message": "timeout"},
        ]
        db_module.mark_slate_success(
            slate_id=row.id,
            candidates=candidates,
            match_runs=match_runs,
            latency_ms=3000,
            discovery_latency_ms=400,
            matches_attempted=2,
            matches_succeeded=1,
        )

        response = client.get(f"/slates/{row.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["matches_attempted"] == 2
        assert body["matches_succeeded"] == 1
        failed = [m for m in body["match_runs"] if m["status"] == "failed"]
        assert len(failed) == 1


class TestSlateAllFailures:
    def test_marks_failed(self, client: TestClient) -> None:
        row = db_module.create_pending_slate_run(
            request_payload={"date": "2026-06-01", "sports": ["soccer"], "max_matches_per_sport": 3, "top_n": 5}
        )
        db_module.mark_slate_failed(
            slate_id=row.id,
            stage="aggregation",
            message="No viable candidates produced from 2 attempted matches",
            latency_ms=4000,
        )

        response = client.get(f"/slates/{row.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "failed"
        assert body["error_stage"] == "aggregation"
        assert "No viable candidates" in body["error_message"]


class TestSlateDiscoveryFailure:
    def test_marks_failed_with_discovery_stage(self, client: TestClient) -> None:
        row = db_module.create_pending_slate_run(
            request_payload={"date": "2026-06-01", "sports": ["soccer"], "max_matches_per_sport": 3, "top_n": 5}
        )
        db_module.mark_slate_failed(
            slate_id=row.id,
            stage="discovery",
            message="LLM provider timeout",
            latency_ms=5000,
        )

        response = client.get(f"/slates/{row.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "failed"
        assert body["error_stage"] == "discovery"
