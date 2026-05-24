"""Tests for the /runs history endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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


def _seed_runs(n: int = 3) -> None:
    from run_ledger import SqliteRunLedger

    ledger = SqliteRunLedger()
    for i in range(n):
        ctx = ledger.start_run(source="cli", request={"match_query": f"team{i} - rival today"})
        ledger.complete_run(ctx.id)


class TestListRunsEndpoint:
    def test_list_runs_returns_200(self, client: TestClient) -> None:
        resp = client.get("/runs")
        assert resp.status_code == 200

    def test_list_runs_returns_empty_initially(self, client: TestClient) -> None:
        resp = client.get("/runs")
        data = resp.json()
        assert data["items"] == []
        assert data["limit"] == 20
        assert data["offset"] == 0

    def test_list_runs_returns_seeded_runs(self, client: TestClient) -> None:
        _seed_runs(3)
        resp = client.get("/runs")
        data = resp.json()
        assert len(data["items"]) == 3

    def test_list_runs_respects_limit(self, client: TestClient) -> None:
        _seed_runs(5)
        resp = client.get("/runs?limit=2")
        data = resp.json()
        assert len(data["items"]) == 2

    def test_list_runs_does_not_expose_request_snapshot(self, client: TestClient) -> None:
        _seed_runs(1)
        resp = client.get("/runs")
        item = resp.json()["items"][0]
        assert "request_snapshot" not in item

    def test_list_runs_includes_status_and_timing(self, client: TestClient) -> None:
        _seed_runs(1)
        resp = client.get("/runs")
        item = resp.json()["items"][0]
        assert item["status"] == "success"
        assert "duration_ms" in item
        assert "started_at" in item


class TestGetRunEndpoint:
    def test_get_run_returns_404_for_unknown(self, client: TestClient) -> None:
        resp = client.get("/runs/nonexistent-id")
        assert resp.status_code == 404

    def test_get_run_returns_full_detail(self, client: TestClient) -> None:
        from run_ledger import SqliteRunLedger

        ledger = SqliteRunLedger()
        ctx = ledger.start_run(source="cli", request={"match_query": "a - b today", "competition": "PL"})
        ledger.record_step(ctx.id, "parse", status="success", duration_ms=10)
        ledger.save_picks(ctx.id, [
            {"player": "P1", "team_id": "T1", "market": "passes", "line": 50.5,
             "direction": "over", "score": 0.8, "confidence": "high",
             "explainability": {"risk_flags": []}},
        ])
        ledger.complete_run(ctx.id)

        resp = client.get(f"/runs/{ctx.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == ctx.id
        assert data["status"] == "success"
        assert data["match_query"] == "a - b today"
        assert len(data["steps"]) == 1
        assert len(data["picks"]) == 1

    def test_get_run_does_not_expose_sensitive_fields(self, client: TestClient) -> None:
        from run_ledger import SqliteRunLedger

        ledger = SqliteRunLedger()
        ctx = ledger.start_run(source="cli", request={
            "match_query": "a - b today",
            "llm_provider": "gemini",
            "llm_model": "gemini-pro",
        })
        ledger.complete_run(ctx.id)

        resp = client.get(f"/runs/{ctx.id}")
        data = resp.json()
        assert "llm_provider" not in data
        assert "llm_model" not in data
        assert "request_snapshot" not in data
