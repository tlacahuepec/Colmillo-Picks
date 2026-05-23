"""Tests for API health endpoint version metadata."""

from __future__ import annotations

import os
from unittest.mock import patch

from fastapi.testclient import TestClient


def _get_client():
    from services.api.main import create_app
    app = create_app()
    return TestClient(app)


class TestHealthzVersionMetadata:
    def test_healthz_includes_version_metadata(self) -> None:
        env = {
            "GEMINI_API_KEY": "x",
            "COLMILLO_VERSION": "0.4.0",
            "COLMILLO_COMMIT": "abc1234",
            "COLMILLO_BUILD_TIME": "2026-05-23T10:00:00Z",
            "COLMILLO_CHANNEL": "stable",
        }
        with patch.dict(os.environ, env):
            client = _get_client()
            response = client.get("/healthz")
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == "0.4.0"
        assert body["commit"] == "abc1234"
        assert body["build_time"] == "2026-05-23T10:00:00Z"
        assert body["channel"] == "stable"

    def test_healthz_missing_metadata_returns_defaults(self) -> None:
        env = {"GEMINI_API_KEY": "x"}
        with patch.dict(os.environ, env, clear=True):
            client = _get_client()
            response = client.get("/healthz")
        body = response.json()
        assert body["version"] == "0.0.0-dev"
        assert body["channel"] == "dev"
        assert body["commit"] == "unknown"

    def test_healthz_does_not_expose_secrets(self) -> None:
        env = {
            "GEMINI_API_KEY": "secret-key-123",
            "COLMILLO_VERSION": "0.4.0",
        }
        with patch.dict(os.environ, env):
            client = _get_client()
            response = client.get("/healthz")
        body_str = response.text
        assert "secret-key-123" not in body_str


class TestVersionEndpoint:
    def test_version_endpoint_returns_metadata(self) -> None:
        env = {
            "GEMINI_API_KEY": "x",
            "COLMILLO_VERSION": "0.4.0",
            "COLMILLO_COMMIT": "def5678",
            "COLMILLO_CHANNEL": "rc",
        }
        with patch.dict(os.environ, env):
            client = _get_client()
            response = client.get("/version")
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == "0.4.0"
        assert body["commit"] == "def5678"
        assert body["channel"] == "rc"

    def test_version_endpoint_defaults(self) -> None:
        env = {"GEMINI_API_KEY": "x"}
        with patch.dict(os.environ, env, clear=True):
            client = _get_client()
            response = client.get("/version")
        body = response.json()
        assert body["version"] == "0.0.0-dev"
        assert body["channel"] == "dev"
