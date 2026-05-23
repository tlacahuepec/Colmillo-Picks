"""Tests for dev environment deployment configuration."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDevDeployment:
    def test_dev_build_workflow_exists(self):
        workflow = REPO_ROOT / ".github" / "workflows" / "dev-build.yml"
        assert workflow.exists()

    def test_dev_build_triggers_on_dev_branch(self):
        workflow = REPO_ROOT / ".github" / "workflows" / "dev-build.yml"
        content = workflow.read_text(encoding="utf-8")
        assert "branches: [dev]" in content

    def test_dev_build_uses_dev_channel(self):
        workflow = REPO_ROOT / ".github" / "workflows" / "dev-build.yml"
        content = workflow.read_text(encoding="utf-8")
        assert "COLMILLO_CHANNEL=dev" in content

    def test_dev_build_does_not_tag_latest(self):
        workflow = REPO_ROOT / ".github" / "workflows" / "dev-build.yml"
        content = workflow.read_text(encoding="utf-8")
        assert ":latest" not in content or "latest" not in content.split("Generate dev tags")[1].split("Build and push")[0]

    def test_dev_deployment_doc_exists(self):
        doc = REPO_ROOT / "docs" / "dev-deployment.md"
        assert doc.exists()

    def test_doc_explains_environment_separation(self):
        doc = REPO_ROOT / "docs" / "dev-deployment.md"
        content = doc.read_text(encoding="utf-8")
        assert "Environment Separation" in content
        assert "channel" in content.lower()
