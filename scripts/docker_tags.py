#!/usr/bin/env python3
"""Generate Docker image tags for a release.

Usage:
    python scripts/docker_tags.py 1.2.3 stable abc1234
    python scripts/docker_tags.py 1.2.3-rc.1 rc abc1234 --registry ghcr.io --image tlacahuepec/colmillo-api
"""

from __future__ import annotations

import sys


def generate_tags(
    *,
    version: str,
    channel: str,
    commit_sha: str,
    registry: str | None = None,
    image_name: str | None = None,
) -> list[str]:
    """Generate Docker image tags for a given release.

    Args:
        version: Semantic version (e.g. "1.2.3", "1.2.3-rc.1").
        channel: Release channel ("stable", "rc", "dev").
        commit_sha: Short commit SHA for traceability.
        registry: Optional registry prefix (e.g. "ghcr.io").
        image_name: Optional image name (e.g. "tlacahuepec/colmillo-api").

    Returns:
        List of tag strings. If registry and image_name are provided,
        tags are fully qualified (registry/image:tag). Otherwise bare tags.
    """
    tags: list[str] = [version, commit_sha]

    if channel == "stable":
        tags.append("latest")
        parts = version.split(".")
        if len(parts) >= 2:
            tags.append(f"{parts[0]}.{parts[1]}")

    if registry and image_name:
        return [f"{registry}/{image_name}:{tag}" for tag in tags]

    return tags


def main() -> int:
    if len(sys.argv) < 4:
        print(
            "Usage: docker_tags.py <version> <channel> <commit_sha> "
            "[--registry REG] [--image NAME]",
            file=sys.stderr,
        )
        return 1

    version = sys.argv[1]
    channel = sys.argv[2]
    commit_sha = sys.argv[3]

    registry = None
    image_name = None

    if "--registry" in sys.argv:
        idx = sys.argv.index("--registry")
        registry = sys.argv[idx + 1]
    if "--image" in sys.argv:
        idx = sys.argv.index("--image")
        image_name = sys.argv[idx + 1]

    tags = generate_tags(
        version=version,
        channel=channel,
        commit_sha=commit_sha,
        registry=registry,
        image_name=image_name,
    )

    for tag in tags:
        print(tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
