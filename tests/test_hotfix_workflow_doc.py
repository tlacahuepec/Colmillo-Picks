"""Tests for docs/hotfix-workflow.md existence and structure."""

from __future__ import annotations

from pathlib import Path


DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"


class TestHotfixWorkflowDoc:
    def test_doc_exists(self):
        assert (DOCS_ROOT / "hotfix-workflow.md").exists()

    def test_covers_required_topics(self):
        content = (DOCS_ROOT / "hotfix-workflow.md").read_text(encoding="utf-8")
        required = [
            "Create hotfix branch from main",
            "Tag the patch release",
            "Backport to dev",
            "Cherry-pick",
            "Versioning Rules",
            "Checklist",
        ]
        for topic in required:
            assert topic in content, f"Missing topic: {topic}"

    def test_hotfix_branches_from_main(self):
        content = (DOCS_ROOT / "hotfix-workflow.md").read_text(encoding="utf-8")
        assert "git checkout main" in content
        assert "fix/" in content

    def test_includes_copy_paste_commands(self):
        content = (DOCS_ROOT / "hotfix-workflow.md").read_text(encoding="utf-8")
        assert "gh pr create --base main" in content
        assert "git tag" in content
        assert "git cherry-pick" in content
