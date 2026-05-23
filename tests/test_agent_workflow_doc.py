"""Tests for docs/agent-workflow.md existence and structure."""

from __future__ import annotations

from pathlib import Path


DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"


class TestAgentWorkflowDoc:
    def test_doc_exists(self):
        assert (DOCS_ROOT / "agent-workflow.md").exists()

    def test_covers_required_topics(self):
        content = (DOCS_ROOT / "agent-workflow.md").read_text(encoding="utf-8")
        required = [
            "Branch from `dev`",
            "Branch Naming",
            "Development Cycle",
            "PR Targets",
            "Pre-Push Checklist",
            "What Agents Must NOT Do",
        ]
        for topic in required:
            assert topic in content, f"Missing topic: {topic}"

    def test_explains_one_issue_per_branch(self):
        content = (DOCS_ROOT / "agent-workflow.md").read_text(encoding="utf-8")
        assert "One issue per feature branch" in content

    def test_includes_copy_paste_commands(self):
        content = (DOCS_ROOT / "agent-workflow.md").read_text(encoding="utf-8")
        assert "git checkout dev && git pull" in content
        assert "gh pr create --base dev" in content
        assert "pytest -q" in content
        assert "ruff check ." in content
