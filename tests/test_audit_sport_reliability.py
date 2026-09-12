from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from audit_sport_reliability import _NBA_FIXTURES, _SOCCER_FIXTURES, _confidence_counts, _summary  # noqa: E402


def test_fixed_llm_fixture_samples_support_the_full_audit_size() -> None:
    assert len(_NBA_FIXTURES) == 10
    assert len(_SOCCER_FIXTURES) == 10


def test_summary_keeps_only_operational_pick_metrics() -> None:
    result = _summary(
        {"players": [{"player_name": "A"}], "lines": {"A": {"points": 20.5}}, "data_quality": {"source": "provider"}},
        [{"score": 0.9, "confidence": "high"}, {"score": 0.5, "confidence": "medium"}],
    )

    assert result["player_count"] == 1
    assert result["prop_line_count"] == 1
    assert result["confidence_counts"] == {"high": 1, "medium": 1, "low": 0, "unknown": 0}
    assert result["score_spread"] == 0.4


def test_unknown_confidence_is_bucketed_without_failing() -> None:
    assert _confidence_counts([{"confidence": "experimental"}]) == {
        "high": 0,
        "medium": 0,
        "low": 0,
        "unknown": 1,
    }


def test_partial_audit_report_records_the_sample_boundary() -> None:
    report = (ROOT / "docs" / "spikes" / "baseball-reliability-audit-2026-09-12.md").read_text(encoding="utf-8")

    assert "10/10 score-stage rejections" in report
    assert "4/4 player-stats provider failures" in report
    assert "Not sampled after the systemic NBA failure stop condition" in report
