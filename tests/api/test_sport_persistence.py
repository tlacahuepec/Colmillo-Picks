"""Tests for sport-aware persistence fields (S03)."""

from __future__ import annotations

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


class TestSportPersistence:
    def test_baseball_run_persists_sport_field(self, client: TestClient) -> None:
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

        detail = client.get(f"/picks/{pick_id}").json()
        assert detail["sport"] == "baseball"

    def test_baseball_run_persists_league(self, client: TestClient) -> None:
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

        detail = client.get(f"/picks/{pick_id}").json()
        assert detail["league"] == "mlb"

    def test_baseball_run_persists_markets(self, client: TestClient) -> None:
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

        detail = client.get(f"/picks/{pick_id}").json()
        assert detail["markets"] == ["hits", "strikeouts"]

    def test_legacy_request_has_no_sport(self, client: TestClient) -> None:
        row = db_module.create_pending_pick_run(
            request_payload={"match_query": "Arsenal - Liverpool 2026-06-15"}
        )
        detail = client.get(f"/picks/{row.id}").json()
        assert detail["sport"] is None

    def test_filter_picks_by_sport(self, client: TestClient) -> None:
        client.post(
            "/picks",
            json={
                "sport": "baseball",
                "home_team": "Yankees",
                "away_team": "Red Sox",
                "event_date": "2026-06-15",
                "league": "mlb",
            },
        )
        client.post(
            "/picks",
            json={
                "sport": "basketball",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "event_date": "2026-06-15",
            },
        )

        baseball_list = client.get("/picks?sport=baseball").json()
        assert all(item["sport"] == "baseball" for item in baseball_list["items"])
        assert len(baseball_list["items"]) == 1

    def test_filter_no_sport_returns_all(self, client: TestClient) -> None:
        client.post(
            "/picks",
            json={
                "sport": "baseball",
                "home_team": "Yankees",
                "away_team": "Red Sox",
                "event_date": "2026-06-15",
                "league": "mlb",
            },
        )
        client.post(
            "/picks",
            json={
                "sport": "basketball",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "event_date": "2026-06-15",
            },
        )

        all_list = client.get("/picks").json()
        assert len(all_list["items"]) >= 2

    def test_migration_idempotent(self, tmp_path) -> None:
        url = f"sqlite:///{tmp_path / 'migration-test.db'}"
        db_module.configure_engine(url)
        db_module.configure_engine(url)
        row = db_module.create_pending_pick_run(
            request_payload={
                "sport": "baseball",
                "league": "mlb",
                "markets": ["hits"],
                "match_query": "test",
            }
        )
        assert row.sport == "baseball"

    def test_sport_appears_in_list_summary(self, client: TestClient) -> None:
        client.post(
            "/picks",
            json={
                "sport": "baseball",
                "home_team": "Yankees",
                "away_team": "Red Sox",
                "event_date": "2026-06-15",
                "league": "mlb",
            },
        )

        items = client.get("/picks").json()["items"]
        baseball_items = [i for i in items if i["sport"] == "baseball"]
        assert len(baseball_items) == 1
