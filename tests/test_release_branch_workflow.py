"""Tests for release branch workflow documentation and CI configuration."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestReleaseBranchWorkflow:
    def test_doc_exists(self):
        doc = REPO_ROOT / "docs" / "release-branch-workflow.md"
        assert doc.exists()

    def test_doc_covers_required_topics(self):
        doc = REPO_ROOT / "docs" / "release-branch-workflow.md"
        content = doc.read_text(encoding="utf-8")
        required = [
            "Create the Release Branch",
            "Tag Release Candidates",
            "Allowed Changes",
            "Merge to Main",
            "Rollback",
        ]
        for topic in required:
            assert topic in content, f"Missing topic: {topic}"

    def test_ci_triggers_on_release_branches(self):
        ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        content = ci.read_text(encoding="utf-8")
        assert "release/**" in content or "release/*" in content

    def test_release_readiness_runs_on_release_branches(self):
        ci = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        content = ci.read_text(encoding="utf-8")
        assert "release/" in content
