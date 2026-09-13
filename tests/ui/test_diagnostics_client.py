"""Diagnostics HTTP contract tests, independent of backend implementation."""

from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest

from services.ui.api_client import APIClientConfig, APIError, PicksAPIClient


def client_for(handler):
    return PicksAPIClient(
        APIClientConfig(base_url="https://api.test", api_key="test-key"),
        transport=httpx.MockTransport(handler),
    )


def test_list_defaults_and_all_filters():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"items": [], "limit": 20, "offset": 0})

    client = client_for(handler)
    assert client.list_diagnostic_operations()["items"] == []
    assert dict(requests[-1].url.params) == {"limit": "20", "offset": "0"}
    client.list_diagnostic_operations(
        limit=50, offset=100, sport="nfl", outcome="failed", service="worker",
        operation_id="legacy pick/+?", since="2026-09-11T00:00:00+00:00",
    )
    request = requests[-1]
    assert request.method == "GET"
    assert request.url.path == "/diagnostics/operations"
    assert request.headers["X-API-Key"] == "test-key"
    assert dict(request.url.params) == {
        "limit": "50", "offset": "100", "sport": "nfl", "outcome": "failed",
        "service": "worker", "operation_id": "legacy pick/+?", "since": "2026-09-11T00:00:00+00:00",
    }
    client.list_diagnostic_operations(sport="", outcome="", service="", operation_id="", since="")
    assert dict(requests[-1].url.params) == {"limit": "20", "offset": "0"}


def test_detail_health_and_binary_export():
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("report.txt", "Diagnostic report\n")
    zip_bytes = buffer.getvalue()
    paths = []

    def handler(request):
        paths.append(request.url.raw_path)
        assert request.headers["X-API-Key"] == "test-key"
        if request.url.path.endswith("/export"):
            return httpx.Response(200, content=zip_bytes, headers={"Content-Type": "application/zip"})
        return httpx.Response(200, json={"operation": {"operation_id": "op-1"}, "events": [], "status": "ok"})

    client = client_for(handler)
    assert client.get_diagnostic_operation("op/?# 1")["events"] == []
    assert client.diagnostics_health()["status"] == "ok"
    assert client.export_diagnostic_operation("op/?# 1") == zip_bytes
    assert paths == [
        b"/diagnostics/operations/op%2F%3F%23%201", b"/diagnostics/health",
        b"/diagnostics/operations/op%2F%3F%23%201/export",
    ]


@pytest.mark.parametrize("method,args", [
    ("list_diagnostic_operations", ()), ("get_diagnostic_operation", ("op-1",)),
    ("diagnostics_health", ()), ("export_diagnostic_operation", ("op-1",)),
])
@pytest.mark.parametrize("status", [401, 404, 503])
def test_diagnostics_preserves_api_error_contract(method, args, status):
    client = client_for(lambda _: httpx.Response(status, json={"detail": "backend detail"}))
    with pytest.raises(APIError) as error:
        getattr(client, method)(*args)
    assert error.value.status_code == status
    assert error.value.detail == "backend detail"


def test_export_non_json_error_and_transport_failure():
    client = client_for(lambda _: httpx.Response(502, text="Bad gateway"))
    with pytest.raises(APIError) as error:
        client.export_diagnostic_operation("op-1")
    assert error.value.detail == "Bad gateway"

    def disconnected(request):
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(httpx.ConnectError):
        client_for(disconnected).export_diagnostic_operation("op-1")
