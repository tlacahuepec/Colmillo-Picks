"""Tests for scripts/docker_tags.py — Docker image tag generation."""

from __future__ import annotations

from scripts.docker_tags import generate_tags


class TestGenerateTags:
    def test_stable_release_includes_version_and_latest(self):
        tags = generate_tags(version="1.2.3", channel="stable", commit_sha="abc1234")
        assert "1.2.3" in tags
        assert "latest" in tags
        assert "abc1234" in tags

    def test_rc_release_excludes_latest(self):
        tags = generate_tags(version="1.2.3-rc.1", channel="rc", commit_sha="abc1234")
        assert "1.2.3-rc.1" in tags
        assert "abc1234" in tags
        assert "latest" not in tags

    def test_dev_channel_excludes_latest(self):
        tags = generate_tags(version="0.0.0-dev", channel="dev", commit_sha="def5678")
        assert "0.0.0-dev" in tags
        assert "def5678" in tags
        assert "latest" not in tags

    def test_stable_includes_major_minor_tag(self):
        tags = generate_tags(version="2.5.1", channel="stable", commit_sha="aaa1111")
        assert "2.5" in tags

    def test_all_tags_are_strings(self):
        tags = generate_tags(version="1.0.0", channel="stable", commit_sha="abc1234")
        assert all(isinstance(t, str) for t in tags)

    def test_no_empty_tags(self):
        tags = generate_tags(version="1.0.0", channel="stable", commit_sha="abc1234")
        assert all(len(t) > 0 for t in tags)

    def test_format_with_registry_prefix(self):
        tags = generate_tags(
            version="1.0.0",
            channel="stable",
            commit_sha="abc1234",
            registry="ghcr.io",
            image_name="tlacahuepec/colmillo-api",
        )
        assert all(t.startswith("ghcr.io/tlacahuepec/colmillo-api:") for t in tags)

    def test_format_without_registry_returns_bare_tags(self):
        tags = generate_tags(version="1.0.0", channel="stable", commit_sha="abc1234")
        assert not any(":" in t for t in tags)
