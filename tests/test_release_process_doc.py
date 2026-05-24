"""Tests for docs/release-process.md existence and structure."""

from __future__ import annotations

from pathlib import Path


DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"


class TestReleaseProcessDoc:
    def test_release_process_doc_exists(self):
        doc = DOCS_ROOT / "release-process.md"
        assert doc.exists()

    def test_contains_required_sections(self):
        doc = DOCS_ROOT / "release-process.md"
        content = doc.read_text(encoding="utf-8")
        required_sections = [
            "Prepare the Release",
            "Trigger the Release",
            "Verify the Release",
            "Rollback",
            "Common Failures",
            "Hotfix",
        ]
        for section in required_sections:
            assert section in content, f"Missing section: {section}"

    def test_references_actual_workflow_files(self):
        doc = DOCS_ROOT / "release-process.md"
        content = doc.read_text(encoding="utf-8")
        assert "release.yml" in content
        assert "publish-docker.yml" in content
        assert "validate_changelog.py" in content
        assert "package_cli.py" in content
