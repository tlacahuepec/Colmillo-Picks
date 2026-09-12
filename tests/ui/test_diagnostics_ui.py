"""Streamlit interaction and sanitization tests for diagnostics."""

from copy import deepcopy
from datetime import date
from io import BytesIO
import json
from unittest.mock import Mock
from zipfile import ZipFile

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from services.ui.api_client import APIError, PicksAPIClient, PickTimeoutError
from services.ui.diagnostics import completeness_text, local_failure_report, safe_text


OPERATION = {
    "operation_id": "op-1", "started_at": "2026-09-11T10:00:00Z",
    "updated_at": "2026-09-11T10:00:01Z", "service": "worker", "sport": "nfl",
    "home_team": "Dallas", "away_team": "New York", "outcome": "failed",
    "duration_ms": 1000, "summary": "The data provider timed out.", "completeness": "partial",
}


def run_app():
    from services.ui.app import main
    main()


def displayed_text(at):
    return "\n".join(
        element.value for kind in ("code", "text", "caption", "markdown", "error", "warning", "info")
        for element in at.get(kind)
    )


@pytest.fixture
def ui(monkeypatch):
    from services.ui import app
    import streamlit as st

    client = Mock(spec=PicksAPIClient)
    client.diagnostics_health.return_value = {"status": "ok", "secret": "never display health metadata"}
    client.list_diagnostic_operations.return_value = {"items": [deepcopy(OPERATION)], "limit": 20, "offset": 0}
    client.get_diagnostic_operation.return_value = {
        "operation": deepcopy(OPERATION), "completeness": {"complete": False},
        "events": [{
            "ts": "2026-09-11T10:00:01Z", "event": "provider_failed", "stage": "collect_data",
            "level": "error", "duration_ms": 950, "outcome": "failed",
            "metadata": {"stack_trace": "Traceback SECRET_STACK", "api_key": "SECRET_KEY"},
        }],
    }
    client.export_diagnostic_operation.return_value = b"PK\x03\x04\x00\xffbackend-zip"
    client.get_hit_rate.return_value = {"total": 0, "hits": 0, "hit_rate": 0, "by_market": []}
    monkeypatch.setattr(app, "_get_client", lambda: client)
    download = Mock(wraps=st.download_button)
    monkeypatch.setattr(st, "download_button", download)
    at = AppTest.from_function(run_app)
    at.session_state["ui_page"] = "Diagnostics"
    return at, client, download


def test_detail_stages_copy_summary_and_backend_zip(ui):
    at, client, downloads = ui
    at.run()
    assert not at.exception
    assert "The data provider timed out." in at.code[0].value
    assert "Partial" in at.code[0].value
    assert "collect data: provider failed" in at.text[0].value
    assert any("950 ms" in c.value for c in at.caption)
    assert "SECRET" not in displayed_text(at)
    client.export_diagnostic_operation.assert_not_called()
    at.button(key="diag_prepare_export").click().run()
    assert not at.exception
    client.export_diagnostic_operation.assert_called_once_with("op-1")
    assert downloads.call_args.kwargs["data"] == client.export_diagnostic_operation.return_value
    assert downloads.call_args.kwargs["mime"] == "application/zip"
    # Preparing and downloading must not re-fetch JSON or poll the operation.
    client.get_diagnostic_operation.assert_called_once_with("op-1")
    client.list_diagnostic_operations.assert_called_once()


def test_filters_pagination_reset_and_manual_refresh(ui):
    at, client, _ = ui
    client.list_diagnostic_operations.return_value["items"] = [
        {**OPERATION, "operation_id": f"op-{n}"} for n in range(20)
    ]
    at.run()
    next(b for b in at.button if b.label == "Next operations").click().run()
    assert client.list_diagnostic_operations.call_args.kwargs["offset"] == 20
    at.date_input(key="diag_since").set_value(date(2026, 9, 10))
    at.selectbox(key="diag_sport").select("NFL")
    at.text_input(key="diag_outcome").set_value("failed")
    at.text_input(key="diag_service").set_value("worker")
    at.text_input(key="diag_operation_id").set_value(" legacy-pick ").run()
    assert not at.exception
    assert client.list_diagnostic_operations.call_args.kwargs == {
        "limit": 20, "offset": 0, "sport": "nfl", "outcome": "failed",
        "service": "worker", "operation_id": "legacy-pick", "since": "2026-09-10T00:00:00+00:00",
    }
    counts = [client.list_diagnostic_operations.call_count, client.get_diagnostic_operation.call_count, client.diagnostics_health.call_count]
    at.button(key="diag_refresh").click().run()
    assert not at.exception
    assert [client.list_diagnostic_operations.call_count, client.get_diagnostic_operation.call_count, client.diagnostics_health.call_count] == [n + 1 for n in counts]


def test_empty_results_and_older_operations(ui):
    at, client, _ = ui
    client.list_diagnostic_operations.return_value["items"] = []
    at.run()
    assert not at.exception
    assert "Older picks or slates" in at.info[0].value
    client.get_diagnostic_operation.assert_not_called()
    assert next(b for b in at.button if b.label == "Next operations").disabled


def test_switching_operations_and_refresh_clear_prepared_export(ui):
    at, client, downloads = ui
    client.list_diagnostic_operations.return_value["items"].append({**OPERATION, "operation_id": "op-2"})
    client.get_diagnostic_operation.side_effect = lambda oid: {
        "operation": {**OPERATION, "operation_id": oid}, "events": [], "completeness": "partial",
    }
    at.run()
    assert "No stage events" in at.info[0].value
    at.button(key="diag_prepare_export").click().run()
    downloads.reset_mock()
    at.selectbox(key="diag_selected").select("op-2").run()
    assert not at.exception
    assert "op-2" in at.code[0].value
    downloads.assert_not_called()
    at.button(key="diag_prepare_export").click().run()
    client.export_diagnostic_operation.assert_called_with("op-2")
    downloads.reset_mock()
    at.button(key="diag_refresh").click().run()
    downloads.assert_not_called()


@pytest.mark.parametrize("completeness,expected", [
    ({"truncated": True, "events_returned": 100}, "more events"),
    ({"has_more": True, "complete": True}, "Partial"),
    ({"retention_may_apply": True}, "older records"),
    ({"complete": False}, "Partial"),
    ({"retention_may_apply": True, "status": "possibly_incomplete"}, "dropped events"),
    ({"retention_may_apply": True, "status": "interrupted"}, "unconfirmed"),
    (True, "Complete"), (None, "not reported"),
])
def test_completeness_explains_snapshot_limits(completeness, expected):
    assert expected in completeness_text(completeness)


def test_link_search_clears_previous_filters(ui):
    at, client, _ = ui
    at.run()
    at.text_input(key="diag_service").set_value("worker")
    at.selectbox(key="diag_sport").select("NFL").run()
    at.session_state["diagnostics_pending_search"] = "legacy-slate"
    at.run()
    assert not at.exception
    assert client.list_diagnostic_operations.call_args.kwargs == {
        "sport": None, "outcome": None, "service": None, "since": None,
        "operation_id": "legacy-slate", "limit": 20, "offset": 0,
    }


@pytest.mark.parametrize("status,expected", [(401, "denied access"), (404, "not found"), (503, "HTTP 503")])
def test_diagnostics_api_errors_are_readable_and_sanitized(ui, status, expected):
    at, client, _ = ui
    client.get_diagnostic_operation.side_effect = APIError(status, "Traceback PRIVATE_SERVER_DETAILS")
    at.run()
    assert not at.exception
    assert expected in at.error[0].value
    assert "PRIVATE_SERVER_DETAILS" not in displayed_text(at)


@pytest.mark.parametrize("method", [
    "diagnostics_health", "list_diagnostic_operations", "get_diagnostic_operation", "export_diagnostic_operation",
])
def test_connection_failure_never_displays_or_downloads_raw_exception(ui, method):
    at, client, downloads = ui
    getattr(client, method).side_effect = httpx.ConnectError(
        "Traceback SECRET_RAW https://user:password@api.test?api_key=SECRET_KEY"
    )
    at.run()
    if method == "export_diagnostic_operation":
        at.button(key="diag_prepare_export").click().run()
    assert not at.exception
    assert at.error
    assert "SECRET" not in displayed_text(at)
    reports = [c.kwargs["data"] for c in downloads.call_args_list if c.kwargs.get("file_name") == "ui-connection-report.zip"]
    assert reports
    for data in reports:
        with ZipFile(BytesIO(data)) as archive:
            report = archive.read("report.json").decode()
        assert "SECRET" not in report and "password" not in report and "Traceback" not in report
        assert json.loads(report)["category"] == "connection"


@pytest.mark.parametrize("error,category", [
    (APIError(401, {"token": "PRIVATE"}), "authentication"),
    (APIError(404, "PRIVATE"), "not_found"),
    (APIError(500, "PRIVATE"), "api_error"),
    (httpx.ReadTimeout("PRIVATE"), "timeout"),
    (PickTimeoutError("PRIVATE"), "polling_timeout"),
    (ValueError("PRIVATE"), "unavailable"),
])
def test_local_report_allowlist(error, category):
    with ZipFile(BytesIO(local_failure_report(error))) as archive:
        data = archive.read("report.json").decode()
    assert "PRIVATE" not in data
    assert json.loads(data)["category"] == category


def test_safe_text_hides_stacks_and_credentials():
    assert "SECRET" not in safe_text("Traceback (most recent call last): SECRET")
    assert "SECRET" not in safe_text('File "SECRET", line 15')
    for value in ("api_key=SECRET", "Authorization: Bearer SECRET", "password: SECRET", "https://SECRET@example.test"):
        assert "SECRET" not in safe_text(value)
    assert safe_text({"stack": "SECRET"}) == "Unknown"


@pytest.mark.parametrize("page,key,record", [
    ("Generate", "generate_diagnostics", {"id": "legacy-pick"}),
    ("Generate", "generate_diagnostics", {"id": "legacy-pick", "operation_id": "op-1"}),
    ("History", "history_diagnostics", {"id": "legacy-pick", "operation_id": "op-1"}),
    ("History", "history_diagnostics", {"id": "legacy-pick"}),
    ("Best Today", "slate_diagnostics", {"id": "legacy-slate", "operation_id": "op-1"}),
    ("Best Today", "slate_pending_diagnostics", {"id": "legacy-slate", "status": "running"}),
])
def test_links_route_to_diagnostics_and_search_existing_ids(ui, page, key, record):
    at, client, _ = ui
    from services.ui import app
    client.create_pick.return_value = record
    detail = {"status": "failed", "match_query": "Dallas vs New York", **record}
    client.list_picks.return_value = {"items": [detail]}
    client.get_pick.return_value = detail
    client.list_slates.return_value = {"items": [detail]}
    client.get_slate.return_value = detail
    at.session_state["ui_page"] = page
    if page == "Best Today":
        at.session_state["selected_slate_id"] = record["id"]
    at.run()
    if page == "Generate":
        at.text_input(key="gen_home").set_value("Dallas")
        at.text_input(key="gen_away").set_value("New York")
        at.checkbox(key="gen_fire_forget").check()
        next(b for b in at.button if b.label == "Generate").click().run()
    assert not at.exception
    at.button(key=key).click().run()
    assert not at.exception
    assert at.sidebar.radio(key="ui_page").value == "Diagnostics"
    assert client.list_diagnostic_operations.call_args.kwargs["operation_id"] == record.get("operation_id", record["id"])
    assert "Diagnostics" in app.PAGES
