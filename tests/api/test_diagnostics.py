import io
import json
import logging
import time
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services import diagnostics as d
from services.api import db
from services.api.diagnostics_routes import admin_router, router
from services.api.logging_config import JsonFormatter
from services.api.middleware import APIKeyAuthMiddleware, RequestLoggingMiddleware
from services.api.sentry import sanitize_sentry_event


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("COLMILLO_API_KEY", "test-key")
    monkeypatch.setenv("COLMILLO_ADMIN_API_KEY", "admin-key")
    monkeypatch.setenv("COLMILLO_RUNS_DB_PATH", str(tmp_path / "runs.db"))
    monkeypatch.setenv("COLMILLO_RATE_LIMIT_PER_HOUR", "1")
    previous_engine, previous_factory = db._engine, db._SessionFactory
    engine = db.configure_engine(f"sqlite:///{tmp_path / 'business.db'}")
    store = d.DiagnosticsStore(tmp_path / "diagnostics.db")
    monkeypatch.setattr(d, "_store", store)
    assert store.ready.wait(3)
    app = FastAPI()
    app.include_router(router)
    app.include_router(admin_router)
    app.add_middleware(APIKeyAuthMiddleware)
    app.add_middleware(RequestLoggingMiddleware, logger=logging.getLogger("diagnostics-test"))
    client = TestClient(app)
    client.headers["X-API-Key"] = "test-key"
    yield client, store
    client.close()
    store.close()
    engine.dispose()
    db._engine, db._SessionFactory = previous_engine, previous_factory


def recorded(store, ident):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        op = store.get_operation(ident)
        if op and op["outcome"] == "failed":
            return
        time.sleep(0.02)
    pytest.fail("record not flushed")


def failed_operation(store):
    with d.operation("generate", sport="nfl", home_team="Saints", away_team="Lions", pick_id="pick-alias") as op:
        try:
            raise TimeoutError("Bearer PRIVATE https://provider.example/?api_key=PRIVATE")
        except TimeoutError as exc:
            d.emit("provider.failed", stage="collect", level="ERROR", **d.error_info(exc))
            op.finish("failed", **d.error_info(exc))
    recorded(store, op.id)
    return op.id


def test_export_and_normal_detail_exclude_frames_and_provider_text(setup):
    client, store = setup
    ident = failed_operation(store)
    detail = client.get(f"/diagnostics/operations/{ident}").json()
    assert detail["operation"]["outcome"] == "failed"
    assert "PRIVATE" not in json.dumps(detail)
    assert "frames" not in json.dumps(detail)
    assert detail["operation"]["metadata"]["error_code"] == "timeout"
    listing = client.get("/diagnostics/operations", params={"operation_id": "pick-alias"}).json()
    assert listing["items"][0]["operation_id"] == ident
    response = client.get(f"/diagnostics/operations/{ident}/export")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        data = b"".join(archive.read(name) for name in archive.namelist())
        assert b'"frames"' not in data and b"PRIVATE" not in data
        assert b"timeout" in data


def test_auth_admin_isolation_and_debug(setup):
    client, store = setup
    ident = failed_operation(store)
    assert client.get("/diagnostics/health", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get(f"/admin/diagnostics/operations/{ident}").status_code == 403
    headers = {"X-Admin-API-Key": "admin-key"}
    data = client.get(f"/admin/diagnostics/operations/{ident}", headers=headers).json()
    assert any(e["metadata"].get("frames") for e in data["events"])
    response = client.post(f"/admin/diagnostics/operations/{ident}/debug", headers=headers)
    assert response.status_code == 200
    assert 0 < store.get_operation(ident)["debug_until"] - time.time() <= 900


def test_reads_separate_from_generation_quota_and_ui_input_restricted(setup):
    client, store = setup
    ident = failed_operation(store)
    for _ in range(4):
        assert client.get("/diagnostics/health").status_code == 200
    payload = {"event": "ui_request_failed", "operation_id": ident}
    assert client.post("/diagnostics/ui-events", json={**payload, "message": "raw prompt"}).status_code == 422
    assert client.post("/diagnostics/ui-events", json=payload).status_code == 202
    assert client.get("/diagnostics/operations", params={"limit": 10000}).status_code == 422


def test_historical_fallback_is_explicit_and_omits_raw_trace(setup):
    client, _ = setup
    row = db.create_pending_pick_run(request_payload={"sport": "nfl"})
    with db.session_scope() as session:
        saved = session.get(db.PickRun, row.id)
        saved.operation_id = None
        saved.trace_json = '{"research_evidence":"PRIVATE"}'
    body = client.get(f"/diagnostics/operations/{row.id}").json()
    assert body["operation"]["completeness"] == "legacy_summary_only"
    assert body["events"] == [] and "PRIVATE" not in json.dumps(body)


@pytest.mark.parametrize("fails", [True, False])
def test_real_nfl_job_reports_failure_or_legitimate_no_picks(setup, monkeypatch, fails):
    from nfl_module import NflModule
    from services.api import main
    def collect(**kwargs):
        if fails:
            raise TimeoutError("Bearer PRIVATE")
        return {"game": None, "players": [], "offers": []}
    monkeypatch.setattr("sport_module.get_sport_module", lambda sport: NflModule(collector=collect))
    payload = {"_sport_module_path": True, "sport": "nfl", "home_team": "saints", "away_team": "lions",
               "event_date": "2026-09-11", "markets": []}
    row = db.create_pending_pick_run(request_payload=payload)
    succeeded = main._execute_pipeline_job(pick_id=row.id, request_dict=payload, bundle_kwargs={})
    saved = db.get_pick_run(row.id)
    assert succeeded is not fails
    assert saved.outcome == ("failed" if fails else "no_picks")
    assert saved.status == ("failed" if fails else "success")
    assert "PRIVATE" not in saved.diagnostics_json
    if fails:
        assert json.loads(saved.diagnostics_json)["error_code"] == "timeout"


def test_formatter_and_sentry_never_serialize_secrets():
    record = logging.LogRecord("test", logging.ERROR, __file__, 1, "provider error %s", ("PRIVATE",), None)
    record.prompt = "PRIVATE"
    record.metadata = {"model": "test-model", "raw_response": "PRIVATE"}
    result = JsonFormatter().format(record)
    assert "PRIVATE" not in result and "test-model" in result
    event = {"request": {"headers": {"authorization": "PRIVATE"}}, "extra": {"prompt": "PRIVATE"},
             "breadcrumbs": ["PRIVATE"], "exception": {"values": [{"type": "TimeoutError", "value": "PRIVATE",
                 "stacktrace": {"frames": [{"filename": "C:/PRIVATE/module.py", "vars": {"secret": "PRIVATE"}}]}}]}}
    result = json.dumps(sanitize_sentry_event(event))
    assert "PRIVATE" not in result and "TimeoutError" in result


def test_logging_store_failure_cannot_replace_business_response(monkeypatch):
    def unavailable():
        raise OSError("storage offline PRIVATE")
    monkeypatch.setattr(d, "get_store", unavailable)
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware, logger=logging.getLogger("fault-test"))

    @app.get("/result")
    def result():
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/result")
    assert response.status_code == 200 and response.json() == {"ok": True}
    assert response.headers["X-Request-Id"]


def test_failed_optional_summary_read_does_not_fail_completed_pipeline(monkeypatch):
    from services.api import main
    monkeypatch.setattr(main, "_execute_pipeline_job_inner", lambda **kwargs: True)
    def unavailable(ident):
        raise OSError("database temporarily unavailable")
    monkeypatch.setattr(db, "get_pick_run", unavailable)
    assert main._execute_pipeline_job(pick_id="saved-pick", request_dict={}, bundle_kwargs={})


def test_partial_pipeline_steps_are_preserved_in_business_outcome(setup):
    row = db.create_pending_pick_run(request_payload={"sport": "soccer"})
    saved = db.mark_pick_success(pick_id=row.id, latency_ms=25, result={
        "scores": [{"rank": 1}], "steps": [{"name": "enrichment", "status": "failed"}],
    })
    assert saved.status == "success" and saved.outcome == "partial"


def test_production_uvicorn_handlers_cannot_bypass_redaction():
    import os
    import subprocess
    import sys
    code = """
import logging.config
from uvicorn.config import LOGGING_CONFIG
from services.api.logging_config import configure_json_logging
logging.config.dictConfig(LOGGING_CONFIG)
configure_json_logging()
try:
    raise ValueError('PRIVATE_EXCEPTION_PAYLOAD')
except ValueError:
    logging.getLogger('uvicorn.error').error('failed %s', 'PRIVATE_ARGUMENT', exc_info=True)
"""
    environment = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    result = subprocess.run([sys.executable, "-c", code], env=environment,
                            capture_output=True, text=True, timeout=10, check=True)
    assert "PRIVATE" not in result.stdout + result.stderr
    record = json.loads(result.stdout)
    assert record["message"] == "log_event" and record["error_type"] == "ValueError"
