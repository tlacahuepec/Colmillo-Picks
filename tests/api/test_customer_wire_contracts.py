"""Customer-facing HTTP contract regressions for the reliability release gate."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from services import diagnostics as diagnostics_module
from services.api import db as db_module
from services.api import main as api_main


class _DiscoveryClient:
    def discover_matches(self, **_: object) -> dict:
        return {
            "date_utc": "2030-06-01",
            "generated_at_utc": "2030-06-01T12:00:00Z",
            "limit_per_sport": 3,
            "results": {
                "soccer": {
                    "matches": [],
                    "error": None,
                    "data_quality": {
                        "status": "unavailable",
                        "verified_count": 0,
                        "rejected_counts": {"missing_citation": 1},
                        "reason": "No verifiable upcoming fixtures were returned.",
                    },
                }
            },
        }


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'contracts.db'}")
    monkeypatch.setenv("COLMILLO_API_KEY", "contract-key")
    monkeypatch.setenv("COLMILLO_WORKER_MODE", "external")
    monkeypatch.setenv("COLMILLO_RUNS_DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.setenv("COLMILLO_CATALOG_DB", str(tmp_path / "catalog.db"))
    store = diagnostics_module.DiagnosticsStore(tmp_path / "diagnostics.db")
    monkeypatch.setattr(diagnostics_module, "_store", store)
    assert store.ready.wait(3)
    test_client = TestClient(api_main.create_app())
    test_client.headers["X-API-Key"] = "contract-key"
    yield test_client
    test_client.close()
    store.close()


def _wait_for_operation(operation_id: str) -> None:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if diagnostics_module.get_store().get_operation(operation_id):
            return
        time.sleep(0.02)
    pytest.fail("diagnostic operation was not persisted")


def test_discovery_contract_distinguishes_unavailable_from_empty(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_main, "_build_match_discovery_client", lambda _: _DiscoveryClient())

    response = client.post("/matches/discover", json={
        "date": "2030-06-01", "sports": ["soccer"], "limit_per_sport": 3,
    })

    assert response.status_code == 200
    body = response.json()
    assert {"date_utc", "generated_at_utc", "limit_per_sport", "results", "cache_status"} <= body.keys()
    result = body["results"]["soccer"]
    assert result["matches"] == []
    assert result["error"] is None
    assert result["data_quality"] == {
        "status": "unavailable",
        "verified_count": 0,
        "rejected_counts": {"missing_citation": 1},
        "reason": "No verifiable upcoming fixtures were returned.",
    }
    assert body["cache_status"] == "uncached"


def test_pick_list_and_detail_contracts_keep_detail_fields_out_of_the_list(client: TestClient) -> None:
    row = db_module.create_pending_pick_run(
        request_payload={"sport": "nfl", "home_team": "Saints", "away_team": "Ravens", "event_date": "2030-06-01"}
    )
    db_module.mark_pick_failed(pick_id=row.id, stage="collect", message="provider unavailable", latency_ms=12)

    listing = client.get("/picks").json()
    item = next(candidate for candidate in listing["items"] if candidate["id"] == row.id)
    assert {"id", "created_at", "display_title", "status", "error_stage", "sport"} <= item.keys()
    assert "scores" not in item and "report_markdown" not in item and "request" not in item

    detail = client.get(f"/picks/{row.id}").json()
    status = client.get(f"/picks/{row.id}/status").json()
    assert {"request", "report_markdown", "scores", "error_message", "error_stage"} <= detail.keys()
    assert {"id", "status", "outcome", "latency_ms", "error_stage", "error_message"} <= status.keys()
    assert detail["display_title"] == "Saints vs Ravens · 2030-06-01"


def test_failed_slate_contract_keeps_missing_counts_null_and_hides_detail_fields_from_list(client: TestClient) -> None:
    row = db_module.create_pending_slate_run(
        request_payload={"date": "2030-06-01", "sports": ["nfl"], "max_matches_per_sport": 3, "top_n": 5}
    )
    db_module.mark_slate_failed(
        slate_id=row.id,
        stage="aggregation",
        message="provider unavailable",
        latency_ms=100,
        match_runs=[{"sport": "nfl", "home_team": "Saints", "away_team": "Ravens", "status": "failed"}],
    )

    listing = client.get("/slates").json()
    item = next(candidate for candidate in listing["items"] if candidate["id"] == row.id)
    assert {"id", "created_at", "status", "request", "outcome"} <= item.keys()
    assert "match_runs" not in item and "matches_attempted" not in item and "candidates" not in item

    detail = client.get(f"/slates/{row.id}").json()
    status = client.get(f"/slates/{row.id}/status").json()
    assert detail["matches_attempted"] is None and detail["matches_succeeded"] is None
    assert len(detail["match_runs"]) == 1
    assert {"id", "status", "outcome", "latency_ms", "error_stage", "error_message"} <= status.keys()


def test_diagnostics_contract_keeps_parent_link_event_time_and_pagination(client: TestClient) -> None:
    with diagnostics_module.operation("slate", sport="nfl") as parent:
        with diagnostics_module.operation("slate_child", sport="nfl", parent_operation_id=parent.id) as child:
            diagnostics_module.emit("collect.started", stage="collect")
            child.finish("no_picks")
        parent.finish("partial")
    _wait_for_operation(child.id)

    listing = client.get("/diagnostics/operations", params={"parent_operation_id": parent.id, "limit": 1}).json()
    assert {"items", "limit", "offset", "has_more", "next_offset"} <= listing.keys()
    item = listing["items"][0]
    assert item["parent_operation_id"] == parent.id

    detail = client.get(f"/diagnostics/operations/{child.id}").json()
    assert {"operation", "events", "completeness"} <= detail.keys()
    assert any("ts" in event for event in detail["events"])
