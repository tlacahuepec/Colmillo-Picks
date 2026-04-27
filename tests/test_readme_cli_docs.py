from __future__ import annotations

import re

from tests.conftest import REPO_ROOT


def _normalize_readme(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text)
    return collapsed.strip().lower()


def test_readme_documents_pipeline_script_and_top_n_usage() -> None:
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    normalized = _normalize_readme(readme_text)

    assert "skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py" in normalized
    assert "--top-n" in normalized


def test_readme_includes_human_explanation_for_top_n_flag() -> None:
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    normalized = _normalize_readme(readme_text)

    explanation_markers = [
        "--top-n controls",
        "--top-n sets",
        "--top-n determines",
        "number of picks",
        "how many picks",
        "top picks to return",
    ]

    assert any(marker in normalized for marker in explanation_markers), (
        "README should explain what --top-n does in prose, not only include it in command examples."
    )


def test_readme_includes_match_query_format_guidance() -> None:
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    normalized = _normalize_readme(readme_text)

    assert "match query" in normalized
    assert any(token in normalized for token in ("today", "tomorrow", "yyyy-mm-dd"))
