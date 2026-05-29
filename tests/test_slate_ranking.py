"""Tests for cross-sport slate candidate normalization and ranking."""

from __future__ import annotations

from slate_ranking import (
    SlateCandidate,
    candidate_from_pick,
    candidates_from_picks,
    rank_slate_candidates,
)


def test_sport_scores_normalize_to_zero_to_100_scale() -> None:
    soccer = candidate_from_pick(_pick(player="Soccer A", score=0.82), sport="soccer")
    basketball = candidate_from_pick(_pick(player="Basketball A", score=0.675), sport="basketball")
    baseball = candidate_from_pick(_pick(player="Baseball A", score=0.91), sport="baseball")

    assert isinstance(soccer, SlateCandidate)
    assert isinstance(basketball, SlateCandidate)
    assert isinstance(baseball, SlateCandidate)
    assert soccer.normalized_score == 82.0
    assert basketball.normalized_score == 67.5
    assert baseball.normalized_score == 91.0


def test_no_bet_picks_are_excluded_from_slate_candidates() -> None:
    picks = [
        _pick(player="Actionable", recommendation="bet", direction="over"),
        _pick(player="Recommendation No Bet", recommendation="no-bet", direction="over"),
        _pick(player="Direction No Bet", recommendation="bet", direction="no-bet"),
    ]

    candidates = candidates_from_picks(picks, sport="soccer")

    assert [candidate.player for candidate in candidates] == ["Actionable"]


def test_candidate_preserves_metadata_and_risk_flags() -> None:
    pick = _pick(
        player="Arsenal CM",
        player_id="ars-8",
        market="passes",
        line=61.5,
        direction="over",
        score=0.84,
        confidence="high",
        risk_flags=["market_disagreement", "low_expected_minutes"],
        source_payload={"model_version": "soccer-v1"},
    )
    source_match = {
        "match_id": "EPL-ARS-LIV-2026-04-27",
        "home_team": "Arsenal",
        "away_team": "Liverpool",
    }

    candidate = candidate_from_pick(
        pick,
        sport="soccer",
        source_match=source_match,
        availability={"final_status": "available"},
    )

    assert candidate is not None
    assert candidate.sport == "soccer"
    assert candidate.source_match == source_match
    assert candidate.player == "Arsenal CM"
    assert candidate.market == "passes"
    assert candidate.line == 61.5
    assert candidate.direction == "over"
    assert candidate.confidence == "high"
    assert candidate.raw_score == 0.84
    assert candidate.normalized_score == 84.0
    assert candidate.risk_flags == ("low_expected_minutes", "market_disagreement")
    assert candidate.availability_status == "available"
    assert candidate.source_pick["source_payload"] == {"model_version": "soccer-v1"}


def test_ranking_is_deterministic_for_equal_scores() -> None:
    candidates = [
        candidate_from_pick(
            _pick(player="B Player", score=0.75, confidence="medium"),
            sport="basketball",
            source_match={"match_id": "nba-2"},
        ),
        candidate_from_pick(
            _pick(player="A Player", score=0.75, confidence="high"),
            sport="soccer",
            source_match={"match_id": "soc-1"},
            availability={"final_status": "available"},
        ),
        candidate_from_pick(
            _pick(player="C Player", score=0.75, confidence="high"),
            sport="baseball",
            source_match={"match_id": "mlb-3"},
            availability={"final_status": "unknown"},
        ),
    ]

    ranked = rank_slate_candidates([candidate for candidate in candidates if candidate is not None])

    assert [candidate.player for candidate in ranked] == ["A Player", "C Player", "B Player"]


def test_missing_availability_missing_score_and_malformed_fields_degrade_safely() -> None:
    candidates = candidates_from_picks(
        [
            {
                "score": None,
                "explainability": {"risk_flags": ["source_missing_score"]},
            },
            _pick(player="Bad Score", score="not-a-number", confidence="high"),
            _pick(player="Percent Score", score=122.0, confidence="medium"),
        ],
        sport="basketball",
    )

    assert len(candidates) == 3
    assert candidates[0].player == "Unknown Player"
    assert candidates[0].market == "unknown"
    assert candidates[0].direction == "unknown"
    assert candidates[0].normalized_score == 0.0
    assert "missing_score" in candidates[0].risk_flags
    assert candidates[0].availability_status == "unknown"
    assert candidates[1].normalized_score == 0.0
    assert "invalid_score" in candidates[1].risk_flags
    assert candidates[2].normalized_score == 100.0
    assert "score_clipped_high" in candidates[2].risk_flags


def _pick(
    *,
    player: str = "Test Player",
    player_id: str = "test-player",
    market: str = "points",
    line: float = 20.5,
    direction: str = "over",
    score: object = 0.8,
    confidence: str = "medium",
    recommendation: str = "bet",
    risk_flags: list[str] | None = None,
    **extra: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "player": player,
        "player_id": player_id,
        "market": market,
        "line": line,
        "direction": direction,
        "score": score,
        "confidence": confidence,
        "recommendation": recommendation,
        "explainability": {"risk_flags": risk_flags or []},
    }
    payload.update(extra)
    return payload
