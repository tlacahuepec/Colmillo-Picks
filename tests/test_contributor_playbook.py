"""Tests for docs/contributor-playbook.md and README linkage."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestContributorPlaybook:
    def test_playbook_exists(self):
        assert (REPO_ROOT / "docs" / "contributor-playbook.md").exists()

    def test_readme_links_to_playbook(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        assert "contributor-playbook.md" in readme

    def test_documents_branch_meanings(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "`main`" in content
        assert "`dev`" in content
        assert "feat/*" in content or "`feat/*`" in content
        assert "release/*" in content or "`release/*`" in content

    def test_main_is_stable(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "stable" in content.lower()
        assert "main" in content

    def test_dev_is_integration(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "integration" in content.lower()

    def test_agents_branch_from_dev(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "Branch from `dev`" in content or "branch from `dev`" in content.lower()

    def test_feature_prs_target_dev(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "--base dev" in content

    def test_release_prs_target_main(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "--base main" in content

    def test_hotfix_starts_from_main(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "git checkout main" in content

    def test_hotfix_backported_to_dev(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "cherry-pick" in content.lower()

    def test_documents_ci_checks(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "pytest" in content
        assert "ruff" in content

    def test_agent_must_not_rules(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "MUST NOT" in content
        assert "force-push" in content.lower() or "Force-push" in content

    def test_references_other_docs(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "release-process.md" in content
        assert "agent-workflow.md" in content

    def test_no_secrets_in_examples(self):
        content = (REPO_ROOT / "docs" / "contributor-playbook.md").read_text(encoding="utf-8")
        assert "sk-" not in content
        assert "ghp_" not in content
        assert "AKIA" not in content
