"""Tests for scripts/validate_changelog.py."""

from __future__ import annotations

import subprocess
import sys

from scripts.validate_changelog import find_version_section


SAMPLE_CHANGELOG = """\
# Changelog

## [Unreleased]

### Added
- Something new

## [0.4.0] — 2026-06-01

### Added
- Feature X

### Changed
- Refactored Y

## [0.3.0] — 2026-05-20

### Added
- Multi-sport pipeline runner

## [0.2.0] — 2026-05-10

### Added
- MVP iteration
"""


class TestFindVersionSection:
    def test_finds_existing_version(self):
        result = find_version_section("0.4.0", SAMPLE_CHANGELOG)
        assert result is not None
        assert "## [0.4.0]" in result
        assert "Feature X" in result

    def test_finds_version_with_v_prefix(self):
        result = find_version_section("v0.3.0", SAMPLE_CHANGELOG)
        assert result is not None
        assert "## [0.3.0]" in result
        assert "Multi-sport pipeline runner" in result

    def test_finds_version_without_prefix(self):
        result = find_version_section("0.3.0", SAMPLE_CHANGELOG)
        assert result is not None
        assert "Multi-sport pipeline runner" in result

    def test_returns_none_for_missing_version(self):
        result = find_version_section("9.9.9", SAMPLE_CHANGELOG)
        assert result is None

    def test_returns_none_for_empty_section(self):
        changelog = "# Changelog\n\n## [1.0.0]\n\n## [0.9.0]\n\n### Added\n- stuff\n"
        result = find_version_section("1.0.0", changelog)
        assert result is None

    def test_section_stops_at_next_version_header(self):
        result = find_version_section("0.4.0", SAMPLE_CHANGELOG)
        assert result is not None
        assert "Multi-sport pipeline runner" not in result

    def test_last_section_captured_to_end(self):
        result = find_version_section("0.2.0", SAMPLE_CHANGELOG)
        assert result is not None
        assert "MVP iteration" in result

    def test_returns_none_for_empty_changelog(self):
        result = find_version_section("1.0.0", "")
        assert result is None

    def test_unreleased_section_findable(self):
        result = find_version_section("Unreleased", SAMPLE_CHANGELOG)
        assert result is not None
        assert "Something new" in result


class TestCLI:
    def test_cli_finds_version_in_real_changelog(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_changelog.py", "0.3.0"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_cli_fails_for_missing_version(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_changelog.py", "99.99.99"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "ERROR" in result.stderr

    def test_cli_fails_without_args(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_changelog.py"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
