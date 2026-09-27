"""Tests for POST /enrichment/audit endpoint (ISSUE-05)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from services.api import main as api_main
from services.api import db as db_module

_TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'colmillo-enrich-audit-test.db'}")


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


def test_enrichment_audit_requires_auth(client: TestClient) -> None:
    client.headers.pop("X-API-Key", None)
    resp = client.post("/enrichment/audit", json={"num_players": 1, "num_attempts": 1, "use_bible_style": False})
    assert resp.status_code == 401


def test_enrichment_audit_validation_error(client: TestClient) -> None:
    resp = client.post("/enrichment/audit", json={"num_players": 0, "num_attempts": 1, "use_bible_style": False})
    assert resp.status_code == 422


def test_enrichment_audit_success(client: TestClient) -> None:
    resp = client.post("/enrichment/audit", json={"num_players": 2, "num_attempts": 1, "use_bible_style": False})
    assert resp.status_code == 200
    data = resp.json()

    assert "summary" in data
    assert "avg_field_fill_rate" in data["summary"]
    assert "avg_source_url_presence" in data["summary"]
    assert "avg_critical_null_rate" in data["summary"]

    assert "players" in data
    assert isinstance(data["players"], list)
    assert len(data["players"]) == 2
    for p in data["players"]:
        assert "player" in p
        assert "fill_rate" in p
        assert "source_urls_presence" in p
        assert "critical_nulls" in p
        assert "confidence_score" in p
        assert "consistency_cv" in p

    assert "sources" in data
    assert isinstance(data["sources"], list)
    for s in data["sources"]:
        assert "domain" in s
        assert "count" in s

    assert "bible_expected" in data
    assert isinstance(data["bible_expected"], list)
    for b in data["bible_expected"]:
        assert "source" in b
        assert "present" in b


def test_enrichment_audit_bible_style(client: TestClient) -> None:
    resp = client.post("/enrichment/audit", json={"num_players": 1, "num_attempts": 1, "use_bible_style": True})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["players"]) == 1
    assert len(data["bible_expected"]) > 0
