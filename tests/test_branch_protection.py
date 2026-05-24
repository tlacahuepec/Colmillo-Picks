"""Tests for branch protection setup script existence and structure."""

from __future__ import annotations

from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parent.parent / "scripts"


class TestBranchProtectionScript:
    def test_setup_script_exists(self):
        script = SCRIPTS_ROOT / "setup_branch_protection.sh"
        assert script.exists()

    def test_script_references_main_and_dev(self):
        script = SCRIPTS_ROOT / "setup_branch_protection.sh"
        content = script.read_text(encoding="utf-8")
        assert "branches/main/protection" in content
        assert "branches/dev/protection" in content

    def test_script_requires_lint_and_tests_checks(self):
        script = SCRIPTS_ROOT / "setup_branch_protection.sh"
        content = script.read_text(encoding="utf-8")
        assert '"Lint"' in content
        assert '"Tests"' in content

    def test_script_requires_pr_reviews(self):
        script = SCRIPTS_ROOT / "setup_branch_protection.sh"
        content = script.read_text(encoding="utf-8")
        assert "required_pull_request_reviews" in content
        assert "required_approving_review_count" in content

    def test_main_requires_docker_build_check(self):
        script = SCRIPTS_ROOT / "setup_branch_protection.sh"
        content = script.read_text(encoding="utf-8")
        assert "Build container images" in content
