"""Tests for basketball report explanations."""

from __future__ import annotations

from basketball_explainer import explain_basketball_pick


class TestBasketballExplanationContent:
    def test_explanation_includes_player_name(self) -> None:
        pick = _full_pick()
        result = explain_basketball_pick(pick)
        assert "LeBron James" in result

    def test_explanation_includes_market_and_direction(self) -> None:
        pick = _full_pick()
        result = explain_basketball_pick(pick)
        assert "points" in result
        assert "over" in result.lower() or "OVER" in result

    def test_explanation_includes_minutes_evidence(self) -> None:
        pick = _full_pick(evidence={"minutes_proj": 36.0})
        result = explain_basketball_pick(pick)
        assert "minutes" in result.lower() or "36" in result

    def test_explanation_includes_usage_evidence(self) -> None:
        pick = _full_pick(evidence={"usage_rate": 0.30})
        result = explain_basketball_pick(pick)
        assert "usage" in result.lower() or "30" in result

    def test_explanation_includes_pace(self) -> None:
        pick = _full_pick(evidence={"pace_factor": 1.08})
        result = explain_basketball_pick(pick)
        assert "pace" in result.lower()

    def test_explanation_includes_recent_form(self) -> None:
        pick = _full_pick(evidence={"points_avg": 24.0, "points_last5": 28.0})
        result = explain_basketball_pick(pick)
        assert "form" in result.lower() or "trend" in result.lower() or "recent" in result.lower()

    def test_explanation_includes_matchup(self) -> None:
        pick = _full_pick(evidence={"opp_rebound_rank": 28})
        result = explain_basketball_pick(pick)
        assert "matchup" in result.lower() or "opponent" in result.lower() or "28" in result


class TestMissingDataInExplanation:
    def test_missing_data_appears_as_risk(self) -> None:
        pick = _full_pick(risk_flags=["missing_data"])
        result = explain_basketball_pick(pick)
        assert "risk" in result.lower() or "missing" in result.lower() or "limited" in result.lower()

    def test_no_evidence_still_produces_explanation(self) -> None:
        pick = {
            "player": "Test Player",
            "market": "points",
            "direction": "over",
            "line": 20.5,
            "score": 0.55,
            "confidence": "low",
            "explainability": {"risk_flags": ["missing_data"]},
        }
        result = explain_basketball_pick(pick)
        assert isinstance(result, str)
        assert len(result) > 0


class TestExplanationFormat:
    def test_explanation_is_nonempty_string(self) -> None:
        pick = _full_pick()
        result = explain_basketball_pick(pick)
        assert isinstance(result, str)
        assert len(result) > 20

    def test_explanation_backed_by_evidence_not_invented(self) -> None:
        pick = _full_pick(evidence={"minutes_proj": 35.0, "usage_rate": 0.28})
        result = explain_basketball_pick(pick)
        assert "35" in result or "minutes" in result.lower()
        assert "28" in result or "usage" in result.lower()


def _full_pick(
    *,
    player: str = "LeBron James",
    market: str = "points",
    direction: str = "over",
    line: float = 25.5,
    score: float = 0.72,
    confidence: str = "high",
    evidence: dict | None = None,
    risk_flags: list[str] | None = None,
) -> dict:
    ev = evidence or {"minutes_proj": 35.0, "usage_rate": 0.28, "points_avg": 25.0, "points_last5": 27.0}
    return {
        "player": player,
        "market": market,
        "direction": direction,
        "line": line,
        "score": score,
        "confidence": confidence,
        "explainability": {
            "risk_flags": risk_flags or [],
            "evidence": ev,
        },
    }
