"""Manual catalog-refresh endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from services.api import db as db_module
from services.api import main as api_main


def test_catalog_refresh_queues_and_reports_completed_job(tmp_path, monkeypatch) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("COLMILLO_API_KEY", "test-key")
    monkeypatch.setenv("COLMILLO_CATALOG_DB", str(tmp_path / "catalog.db"))

    def complete(store, *, job_id: str, run_date: str) -> None:
        assert run_date == "2026-09-15"
        assert store.update_job(job_id, now="2026-09-15T00:00:01Z", state="success", summary='{"snapshots": 1}')

    monkeypatch.setattr(api_main, "run_fanatics_refresh", complete)
    client = TestClient(api_main.create_app())
    client.headers.update({"X-API-Key": "test-key"})

    response = client.post("/catalog/refresh", json={"date": "2026-09-15"})

    assert response.status_code == 202
    job = client.get(f"/catalog/jobs/{response.json()['job_id']}")
    assert job.status_code == 200
    assert job.json()["state"] == "success"
    assert job.json()["summary"] == {"snapshots": 1}


def test_catalog_refresh_rejects_invalid_date(tmp_path, monkeypatch) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("COLMILLO_API_KEY", "test-key")
    monkeypatch.setenv("COLMILLO_CATALOG_DB", str(tmp_path / "catalog.db"))
    client = TestClient(api_main.create_app())
    client.headers.update({"X-API-Key": "test-key"})

    response = client.post("/catalog/refresh", json={"date": "15-09-2026"})

    assert response.status_code == 422


def test_catalog_settings_can_enable_a_discovered_sport(tmp_path, monkeypatch) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("COLMILLO_API_KEY", "test-key")
    monkeypatch.setenv("COLMILLO_CATALOG_DB", str(tmp_path / "catalog.db"))
    client = TestClient(api_main.create_app())
    client.headers.update({"X-API-Key": "test-key"})

    initial = client.get("/catalog/settings")
    assert initial.status_code == 200
    assert {item["sport"] for item in initial.json()["items"] if item["enabled"]} == {
        "baseball", "basketball", "nfl", "soccer"
    }

    updated = client.put("/catalog/settings/tennis", json={"enabled": True})
    assert updated.status_code == 200
    assert updated.json() == {"sport": "tennis", "enabled": True}
