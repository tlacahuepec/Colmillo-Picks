from services.catalog.storage import CatalogStore


def test_catalog_health_reports_storage_and_job_state_counts(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    assert store.health()["available"] is True
    assert store.health()["jobs_by_state"] == {}
    assert store.acquire_job(job_id="job-1", run_date="2026-09-11", now="2026-09-11T06:00:00Z", lease_until="2026-09-11T06:10:00Z")
    assert store.health()["jobs_by_state"] == {"running": 1}
