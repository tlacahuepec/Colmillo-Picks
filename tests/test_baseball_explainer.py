"""Tests for MLB explanation service (deterministic + LLM with hallucination guard)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from baseball_explainer import (
    build_deterministic_explanation,
    build_llm_explanation,
    validate_explanation_against_inputs,
    explain_picks,
    BANNED_GUARANTEE_WORDS,
)


def _sample_scored_pick(**overrides: Any) -> dict[str, Any]:
    base = {
        "player": "Aaron Judge",
        "market": "home_runs",
        "line": 0.5,
        "direction": "over",
        "score": 0.82,
        "confidence": "high",
        "explainability": {
            "risk_flags": [],
            "top_contributing_factors": [
                {"factor": "ballpark_factor", "score": 0.9, "weight": 0.2},
                {"factor": "pitcher_matchup_handedness", "score": 0.62, "weight": 0.18},
                {"factor": "recent_form_momentum", "score": 0.7, "weight": 0.15},
            ],
        },
    }
    base.update(overrides)
    return base


def _sample_input_context() -> dict[str, Any]:
    return {
        "players": ["Aaron Judge", "Juan Soto", "Rafael Devers"],
        "stats": {
            "Aaron Judge": {"hr_per_game": 0.35, "hr_last5_per_game": 0.6},
        },
        "weather": {"temp_f": 85, "wind_direction": "out to center"},
        "ballpark": "Yankee Stadium",
    }


class TestDeterministicExplanation:
    def test_returns_non_empty_string(self):
        pick = _sample_scored_pick()
        explanation = build_deterministic_explanation(pick)
        assert isinstance(explanation, str)
        assert len(explanation) > 0

    def test_includes_player_name(self):
        pick = _sample_scored_pick()
        explanation = build_deterministic_explanation(pick)
        assert "Aaron Judge" in explanation

    def test_includes_market_and_direction(self):
        pick = _sample_scored_pick()
        explanation = build_deterministic_explanation(pick)
        assert "home_runs" in explanation
        assert "over" in explanation.lower()

    def test_includes_top_factors(self):
        pick = _sample_scored_pick()
        explanation = build_deterministic_explanation(pick)
        assert "ballpark_factor" in explanation

    def test_includes_confidence(self):
        pick = _sample_scored_pick()
        explanation = build_deterministic_explanation(pick)
        assert "high" in explanation.lower()

    def test_includes_no_guarantee_disclaimer(self):
        pick = _sample_scored_pick()
        explanation = build_deterministic_explanation(pick)
        assert "not a prediction" in explanation.lower() or "no guarantee" in explanation.lower()

    def test_no_bet_pick_explains_reason(self):
        pick = _sample_scored_pick(
            confidence="low",
            explainability={
                "risk_flags": ["missing_data"],
                "top_contributing_factors": [],
            },
        )
        explanation = build_deterministic_explanation(pick, no_bet=True, no_bet_reason="missing_probable_pitcher")
        assert "missing_probable_pitcher" in explanation.lower() or "no-bet" in explanation.lower()

    def test_no_banned_guarantee_words(self):
        pick = _sample_scored_pick()
        explanation = build_deterministic_explanation(pick)
        explanation_lower = explanation.lower()
        for word in BANNED_GUARANTEE_WORDS:
            assert word not in explanation_lower, f"Banned word '{word}' found in explanation"


class TestHallucinationGuard:
    def test_valid_explanation_passes(self):
        context = _sample_input_context()
        explanation = "Aaron Judge benefits from favorable ballpark conditions at Yankee Stadium."
        result = validate_explanation_against_inputs(explanation, context)
        assert result.valid is True

    def test_rejects_unknown_player_reference(self):
        context = _sample_input_context()
        explanation = "Mike Trout has been hitting well lately, making this a strong pick."
        result = validate_explanation_against_inputs(explanation, context)
        assert result.valid is False
        assert "player" in result.reason.lower() or "hallucination" in result.reason.lower()

    def test_rejects_banned_guarantee_language(self):
        context = _sample_input_context()
        explanation = "Aaron Judge is guaranteed to hit a home run today."
        result = validate_explanation_against_inputs(explanation, context)
        assert result.valid is False

    def test_allows_empty_context_players_gracefully(self):
        context: dict[str, Any] = {"players": [], "stats": {}}
        explanation = "Based on available data, this pick has moderate confidence."
        result = validate_explanation_against_inputs(explanation, context)
        assert result.valid is True


class TestLLMExplanation:
    def test_calls_llm_client(self):
        mock_client = MagicMock()
        mock_client.generate_structured.return_value = {
            "explanation": "Judge has favorable conditions at Yankee Stadium with wind blowing out."
        }
        pick = _sample_scored_pick()
        context = _sample_input_context()

        explanation = build_llm_explanation(
            pick=pick,
            input_context=context,
            llm_client=mock_client,
        )
        assert mock_client.generate_structured.called
        assert "Judge" in explanation or "Yankee" in explanation

    def test_falls_back_to_deterministic_on_llm_error(self):
        mock_client = MagicMock()
        mock_client.generate_structured.side_effect = RuntimeError("LLM unavailable")
        pick = _sample_scored_pick()
        context = _sample_input_context()

        explanation = build_llm_explanation(
            pick=pick,
            input_context=context,
            llm_client=mock_client,
        )
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "Aaron Judge" in explanation

    def test_falls_back_when_hallucination_detected(self):
        mock_client = MagicMock()
        mock_client.generate_structured.return_value = {
            "explanation": "Mike Trout is on fire this season."
        }
        pick = _sample_scored_pick()
        context = _sample_input_context()

        explanation = build_llm_explanation(
            pick=pick,
            input_context=context,
            llm_client=mock_client,
        )
        assert "Mike Trout" not in explanation
        assert "Aaron Judge" in explanation

    def test_prompt_includes_context_only_instruction(self):
        mock_client = MagicMock()
        mock_client.generate_structured.return_value = {
            "explanation": "Judge favored by ballpark."
        }
        pick = _sample_scored_pick()
        context = _sample_input_context()

        build_llm_explanation(pick=pick, input_context=context, llm_client=mock_client)
        call_kwargs = mock_client.generate_structured.call_args[1]
        system_prompt = call_kwargs["system_prompt"]
        assert "only" in system_prompt.lower() and "supplied" in system_prompt.lower()


class TestExplainPicks:
    def test_deterministic_mode(self):
        picks = [_sample_scored_pick(), _sample_scored_pick(player="Juan Soto", market="hits")]
        context = _sample_input_context()

        results = explain_picks(picks=picks, input_context=context, use_llm=False)
        assert len(results) == 2
        assert all(r["explanation"] for r in results)
        assert all(r["explanation_status"] == "deterministic" for r in results)

    def test_llm_mode_with_mock(self):
        mock_client = MagicMock()
        mock_client.generate_structured.return_value = {
            "explanation": "Aaron Judge benefits from favorable ballpark and wind conditions."
        }
        picks = [_sample_scored_pick()]
        context = _sample_input_context()

        results = explain_picks(
            picks=picks, input_context=context, use_llm=True, llm_client=mock_client
        )
        assert len(results) == 1
        assert results[0]["explanation_status"] in ("llm_success", "deterministic_fallback")

    def test_cannot_add_picks_scorer_didnt_select(self):
        picks = [_sample_scored_pick()]
        context = _sample_input_context()

        results = explain_picks(picks=picks, input_context=context, use_llm=False)
        assert len(results) == len(picks)

    def test_cannot_remove_no_bet_designation(self):
        pick = _sample_scored_pick(confidence="low")
        pick["explainability"]["risk_flags"] = ["no_bet_missing_pitcher"]
        picks = [pick]
        context = _sample_input_context()

        results = explain_picks(
            picks=picks, input_context=context, use_llm=False, no_bet_picks={"Aaron Judge:home_runs"}
        )
        matching = [r for r in results if r["player"] == "Aaron Judge" and r["market"] == "home_runs"]
        assert matching[0].get("no_bet") is True
