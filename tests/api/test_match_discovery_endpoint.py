"""Tests for the sport-aware match discovery API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.api import db as db_module
from services.api import main as api_main


_TEST_API_KEY = "match-discovery-key"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'colmillo-discovery.db'}")
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


class _FakeDiscoveryClient:
    def __init__(self, response: dict) -> None:
        self._response = response
        self.calls: list[dict] = []

    def discover_matches(
        self,
        *,
        date_utc: str,
        sports: list[str],
        limit_per_sport: int,
    ) -> dict:
        self.calls.append({
            "date_utc": date_utc,
            "sports": sports,
            "limit_per_sport": limit_per_sport,
        })
        return self._response


def _api_response() -> dict:
    return {
        "date_utc": "2026-06-01",
        "generated_at_utc": "2026-06-01T12:00:00Z",
        "limit_per_sport": 3,
        "results": {
            "soccer": {
                "matches": [
                    {
                        "sport": "soccer",
                        "home_team": "Arsenal",
                        "away_team": "Liverpool",
                        "event_date": "2026-06-01",
                        "league": "premier_league",
                        "competition": "Premier League",
                        "kickoff_utc": "2026-06-01T19:00:00Z",
                        "importance": "high",
                        "notes": "Title-race leverage",
                        "source_provider": "fake",
                        "source_model": "fake-model",
                        "sources": [{"label": "fixture list", "url": "https://example.com"}],
                        "data_quality": {"confidence": "medium", "missing_fields": []},
                    }
                ],
                "error": None,
                "data_quality": {"status": "ok"},
            }
        },
    }


def test_post_matches_discover_returns_grouped_sport_matches(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    fake_client = _FakeDiscoveryClient(_api_response())
    monkeypatch.setattr(api_main, "_build_match_discovery_client", lambda _: fake_client)

    response = client.post(
        "/matches/discover",
        json={
            "date": "2026-06-01",
            "sports": ["soccer"],
            "limit_per_sport": 3,
            "llm_provider": "gemini",
            "llm_model": "gemini-2.5-flash",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"]["soccer"]["matches"][0]["home_team"] == "Arsenal"
    assert body["results"]["soccer"]["matches"][0]["away_team"] == "Liverpool"
    assert body["results"]["soccer"]["matches"][0]["source_provider"] == "fake"
    assert body["results"]["soccer"]["matches"][0]["data_quality"]["confidence"] == "medium"
    assert fake_client.calls == [{
        "date_utc": "2026-06-01",
        "sports": ["soccer"],
        "limit_per_sport": 3,
    }]


def test_post_matches_discover_returns_400_for_unsupported_sport(client: TestClient) -> None:
    response = client.post(
        "/matches/discover",
        json={"date": "2026-06-01", "sports": ["cricket"], "limit_per_sport": 3},
    )

    assert response.status_code == 400
    assert "cricket" in response.json()["detail"]


def test_post_matches_discover_validates_limit_per_sport(client: TestClient) -> None:
    response = client.post(
        "/matches/discover",
        json={"date": "2026-06-01", "sports": ["soccer"], "limit_per_sport": 6},
    )

    assert response.status_code == 422
    assert "limit_per_sport" in str(response.json()["detail"])


def test_post_matches_discover_preserves_partial_sport_errors(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    response_payload = _api_response()
    response_payload["results"]["basketball"] = {
        "matches": [],
        "error": "provider timeout",
        "data_quality": {"status": "error"},
    }
    fake_client = _FakeDiscoveryClient(response_payload)
    monkeypatch.setattr(api_main, "_build_match_discovery_client", lambda _: fake_client)

    response = client.post(
        "/matches/discover",
        json={
            "date": "2026-06-01",
            "sports": ["soccer", "basketball"],
            "limit_per_sport": 3,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"]["soccer"]["matches"]
    assert body["results"]["basketball"]["matches"] == []
    assert body["results"]["basketball"]["error"] == "provider timeout"
