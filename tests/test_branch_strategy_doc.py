"""Tests for docs/branch-strategy.md existence and structure."""

from __future__ import annotations

from pathlib import Path


DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"


class TestBranchStrategyDoc:
    def test_branch_strategy_doc_exists(self):
        doc = DOCS_ROOT / "branch-strategy.md"
        assert doc.exists()

    def test_contains_required_sections(self):
        doc = DOCS_ROOT / "branch-strategy.md"
        content = doc.read_text(encoding="utf-8")
        required = [
            "Branch Roles",
            "Branch Naming",
            "Workflow Rules",
            "What NOT to do",
            "Merge Strategy",
            "Review Expectations",
            "Release Flow",
            "Hotfix Flow",
            "Agent-Specific Rules",
        ]
        for section in required:
            assert section in content, f"Missing section: {section}"

    def test_documents_dev_as_integration_branch(self):
        doc = DOCS_ROOT / "branch-strategy.md"
        content = doc.read_text(encoding="utf-8")
        assert "branch from `dev`" in content.lower() or "branch from dev" in content.lower()

    def test_prohibits_direct_main_pushes(self):
        doc = DOCS_ROOT / "branch-strategy.md"
        content = doc.read_text(encoding="utf-8")
        assert "NOT push directly to `main`" in content or "never directly to `main`" in content.lower()
