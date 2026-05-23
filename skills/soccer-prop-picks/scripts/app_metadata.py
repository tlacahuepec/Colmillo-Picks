"""App version and channel metadata.

Reads build metadata from environment variables (injected by CI/CD)
with safe fallback defaults for local development.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


VALID_CHANNELS = ("dev", "rc", "stable")


@dataclass(frozen=True)
class AppMetadata:
    version: str
    commit: str
    build_time: str
    branch: str
    channel: str


def get_app_metadata() -> AppMetadata:
    version = os.environ.get("COLMILLO_VERSION", "") or "0.0.0-dev"
    commit = os.environ.get("COLMILLO_COMMIT", "") or "unknown"
    build_time = os.environ.get("COLMILLO_BUILD_TIME", "") or "unknown"
    branch = os.environ.get("COLMILLO_BRANCH", "") or "unknown"
    channel = os.environ.get("COLMILLO_CHANNEL", "") or "dev"

    if channel not in VALID_CHANNELS:
        channel = "dev"

    return AppMetadata(
        version=version,
        commit=commit,
        build_time=build_time,
        branch=branch,
        channel=channel,
    )
