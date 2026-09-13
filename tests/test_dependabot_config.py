from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dependabot_covers_requested_ecosystems_with_reviewable_groups() -> None:
    config = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")

    assert "package-ecosystem: pip" in config
    assert "package-ecosystem: github-actions" in config
    assert "package-ecosystem: docker" in config
    assert config.count("interval: weekly") == 3
    assert "update-types: [minor, patch]" in config
    assert "open-pull-requests-limit: 5" in config


def test_dependency_update_policy_preserves_ci_and_review() -> None:
    policy = (ROOT / "docs" / "dependency-updates.md").read_text(encoding="utf-8")

    assert "Security updates are never auto-merged" in policy
    assert "Ruff, Pyright, pytest" in policy
