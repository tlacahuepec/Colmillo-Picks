"""Tests for ``services.ui.api_client``.

We point the client at the real FastAPI app via httpx's ``ASGITransport`` so
the tests exercise routing, auth, and persistence end-to-end without spinning
up a network server.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from services.api import db as db_module
from services.api import main as api_main
from services.ui.api_client import APIClientConfig, APIError, PicksAPIClient


_TEST_API_KEY = "ui-test-key"


def _build_test_transport(app) -> httpx.MockTransport:
    """Bridge httpx requests into the FastAPI TestClient.

    httpx 0.28's ``ASGITransport`` is async-only, so we route via the
    synchronous ``TestClient`` to keep these tests simple.
    """
    fastapi_client = TestClient(app)
    fastapi_client.headers.clear()

    def handler(request: httpx.Request) -> httpx.Response:
        response = fastapi_client.request(
            request.method,
            str(request.url),
            content=request.content,
            headers=dict(request.headers),
        )
        return httpx.Response(
            status_code=response.status_code,
            headers=dict(response.headers),
            content=response.content,
        )

    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'colmillo-ui-test.db'}")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> PicksAPIClient:
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    monkeypatch.delenv("COLMILLO_UI_ORIGIN", raising=False)

    def fake_build_bundle(**_: Any) -> dict[str, Any]:
        return {"deps": "bundle"}

    def fake_run_pipeline(*, request: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
        return {
            "report_markdown": f"# Report for {request['match_query']}",
            "scores": [{"player": "A"}],
            "trace": {"llm_status": "not_requested"},
            "match_inputs": {"match": {"id": "X", "fixture_status": "scheduled"}},
        }

    monkeypatch.setattr(api_main, "build_dependency_bundle", fake_build_bundle)
    monkeypatch.setattr(api_main, "run_pipeline_with_payload", fake_run_pipeline)

    transport = _build_test_transport(api_main.create_app())
    config = APIClientConfig(base_url="http://testserver", api_key=_TEST_API_KEY)
    return PicksAPIClient(config, transport=transport)


def test_client_uses_env_for_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLMILLO_API_URL", "http://api.example.test/")
    monkeypatch.setenv("COLMILLO_API_KEY", "secret")

    config = APIClientConfig.from_env()

    assert config.base_url == "http://api.example.test"
    assert config.api_key == "secret"


def test_health_returns_status(client: PicksAPIClient) -> None:
    body = client.health()

    assert body["status"] == "ok"
    assert "providers" in body


def test_create_pick_round_trips_through_api(client: PicksAPIClient) -> None:
    result = client.create_pick(
        {"match_query": "juve - milan today", "league": "Serie A", "top_n": 3}
    )

    assert result["id"]
    assert result["report_markdown"].startswith("# Report for juve - milan today")
    assert result["scores"] == [{"player": "A"}]


def test_list_picks_paginates(client: PicksAPIClient) -> None:
    for label in ("a", "b", "c"):
        client.create_pick({"match_query": f"juve - milan today {label}"})

    page = client.list_picks(limit=2, offset=0)

    assert page["limit"] == 2
    assert page["offset"] == 0
    assert len(page["items"]) == 2


def test_get_pick_returns_stored_payload(client: PicksAPIClient) -> None:
    created = client.create_pick({"match_query": "juve - milan today"})

    detail = client.get_pick(created["id"])

    assert detail["id"] == created["id"]
    assert detail["match_query"] == "juve - milan today"
    assert detail["report_markdown"].startswith("# Report for juve - milan today")


def test_get_unknown_pick_raises_api_error(client: PicksAPIClient) -> None:
    with pytest.raises(APIError) as excinfo:
        client.get_pick("does-not-exist")

    assert excinfo.value.status_code == 404


def test_missing_api_key_raises_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    transport = _build_test_transport(api_main.create_app())
    bad_client = PicksAPIClient(
        APIClientConfig(base_url="http://testserver", api_key=""),
        transport=transport,
    )

    with pytest.raises(APIError) as excinfo:
        bad_client.create_pick({"match_query": "juve - milan today"})

    assert excinfo.value.status_code == 401
