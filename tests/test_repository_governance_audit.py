from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_governance_audit_records_controls_and_unresolved_decisions() -> None:
    audit = (ROOT / "docs" / "repository-governance-audit-2026-09-12.md").read_text(encoding="utf-8")

    assert "## Verified controls" in audit
    assert "## Findings requiring maintainer decision" in audit
    assert "squash-only" in audit
    assert "do not delete branches automatically" in audit
    assert "## Follow-up checklist" in audit
