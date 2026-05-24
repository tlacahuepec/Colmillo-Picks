"""Tests for app version and channel metadata."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app_metadata import AppMetadata, get_app_metadata, VALID_CHANNELS


class TestAppMetadataDefaults:
    def test_missing_values_return_safe_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            meta = get_app_metadata()
        assert meta.version == "0.0.0-dev"
        assert meta.commit == "unknown"
        assert meta.build_time == "unknown"
        assert meta.branch == "unknown"
        assert meta.channel == "dev"

    def test_metadata_has_all_fields(self) -> None:
        meta = get_app_metadata()
        assert isinstance(meta, AppMetadata)
        assert hasattr(meta, "version")
        assert hasattr(meta, "commit")
        assert hasattr(meta, "build_time")
        assert hasattr(meta, "branch")
        assert hasattr(meta, "channel")


class TestAppMetadataFromEnv:
    def test_reads_values_from_env(self) -> None:
        env = {
            "COLMILLO_VERSION": "0.4.0",
            "COLMILLO_COMMIT": "abc1234",
            "COLMILLO_BUILD_TIME": "2026-05-23T10:00:00Z",
            "COLMILLO_BRANCH": "main",
            "COLMILLO_CHANNEL": "stable",
        }
        with patch.dict(os.environ, env, clear=True):
            meta = get_app_metadata()
        assert meta.version == "0.4.0"
        assert meta.commit == "abc1234"
        assert meta.build_time == "2026-05-23T10:00:00Z"
        assert meta.branch == "main"
        assert meta.channel == "stable"

    def test_partial_env_uses_defaults_for_missing(self) -> None:
        env = {"COLMILLO_VERSION": "0.3.1"}
        with patch.dict(os.environ, env, clear=True):
            meta = get_app_metadata()
        assert meta.version == "0.3.1"
        assert meta.commit == "unknown"
        assert meta.channel == "dev"


class TestChannelValidation:
    def test_valid_channels_accepted(self) -> None:
        for channel in VALID_CHANNELS:
            env = {"COLMILLO_CHANNEL": channel}
            with patch.dict(os.environ, env, clear=True):
                meta = get_app_metadata()
            assert meta.channel == channel

    def test_invalid_channel_normalized_to_dev(self) -> None:
        env = {"COLMILLO_CHANNEL": "nightly"}
        with patch.dict(os.environ, env, clear=True):
            meta = get_app_metadata()
        assert meta.channel == "dev"

    def test_empty_channel_defaults_to_dev(self) -> None:
        env = {"COLMILLO_CHANNEL": ""}
        with patch.dict(os.environ, env, clear=True):
            meta = get_app_metadata()
        assert meta.channel == "dev"


class TestMetadataImmutability:
    def test_metadata_is_frozen(self) -> None:
        meta = get_app_metadata()
        with pytest.raises((AttributeError, TypeError)):
            meta.version = "hacked"
