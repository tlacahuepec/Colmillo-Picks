"""Tests for LangGraph enrichment graph node functions (S03, #255)."""

from __future__ import annotations

from unittest.mock import MagicMock

from llm.client import GroundingMetadataResult, GroundingSource, GroundingSupport
from llm.langgraph_enrichment import (
    attach_grounding_node,
    invoke_llm_node,
    merge_with_scores_node,
    prepare_context_node,
    validate_output_node,
)


def _make_grounding_metadata():
    return GroundingMetadataResult(
        sources=(
            GroundingSource(url="https://example.com/stats", title="Stats Page"),
        ),
        supports=(
            GroundingSupport(start_index=0, end_index=10, text="sample", source_indices=(0,)),
        ),
        web_search_queries=("player stats 2026",),
    )


def _sample_state():
    return {
        "scored_payload": {
            "scores": [
                {"player_id": "player_1", "market": "points", "score": 0.8}
            ],
            "trace": {"notes": []},
        },
        "match_inputs": {"home_team": "Lakers", "away_team": "Celtics"},
        "top_n": 5,
        "transitions": [],
    }


class TestPrepareContextNode:
    def test_builds_prompt_from_inputs(self):
        state = _sample_state()
        updates = prepare_context_node(state)

        assert "prompt" in updates
        assert "system" in updates["prompt"]
        assert "user" in updates["prompt"]
        assert "transitions" in updates
        assert "prepare_context" in updates["transitions"]

    def test_prompt_contains_scored_props(self):
        state = _sample_state()
        updates = prepare_context_node(state)

        assert "player_1" in updates["prompt"]["user"]


class TestInvokeLlmNode:
    def test_stores_raw_output_in_state(self):
        mock_client = MagicMock()
        mock_client.generate_structured.return_value = {"explanations": []}
        mock_client.last_grounding_metadata = None

        state = _sample_state()
        state["prompt"] = {"system": "sys", "user": "usr"}
        state["transitions"] = []

        updates = invoke_llm_node(state, client=mock_client)

        assert updates["raw_output"] == {"explanations": []}
        assert "invoke_llm" in updates["transitions"]

    def test_captures_grounding_metadata_when_available(self):
        grounding = _make_grounding_metadata()
        mock_client = MagicMock()
        mock_client.generate_structured.return_value = {"explanations": []}
        mock_client.last_grounding_metadata = grounding

        state = _sample_state()
        state["prompt"] = {"system": "sys", "user": "usr"}
        state["transitions"] = []

        updates = invoke_llm_node(state, client=mock_client)

        assert updates["grounding_metadata"] is grounding

    def test_sets_error_on_failure(self):
        mock_client = MagicMock()
        mock_client.generate_structured.side_effect = RuntimeError("API timeout")
        mock_client.last_grounding_metadata = None

        state = _sample_state()
        state["prompt"] = {"system": "sys", "user": "usr"}
        state["transitions"] = []

        updates = invoke_llm_node(state, client=mock_client)

        assert "error" in updates
        assert "API timeout" in updates["error"]
        assert "invoke_llm" in updates["transitions"]

    def test_grounding_none_when_client_lacks_attribute(self):
        mock_client = MagicMock(spec=[])
        mock_client.generate_structured = MagicMock(return_value={"explanations": []})

        state = _sample_state()
        state["prompt"] = {"system": "sys", "user": "usr"}
        state["transitions"] = []

        updates = invoke_llm_node(state, client=mock_client)

        assert updates.get("grounding_metadata") is None


class TestValidateOutputNode:
    def test_parses_raw_output_into_explanations(self):
        state = _sample_state()
        state["raw_output"] = {
            "explanations": [
                {
                    "player_id": "player_1",
                    "market_type": "points",
                    "recommended_side": "over",
                    "confidence_band": "high",
                    "rationale": "Strong recent form",
                    "risk_flags": [],
                }
            ]
        }
        state["transitions"] = []

        updates = validate_output_node(state)

        assert "explanations" in updates
        assert len(updates["explanations"]) == 1
        assert updates["explanations"][0]["player_id"] == "player_1"
        assert "validate_output" in updates["transitions"]

    def test_sets_error_on_invalid_output(self):
        state = _sample_state()
        state["raw_output"] = {"invalid": "data"}
        state["transitions"] = []

        updates = validate_output_node(state)

        assert "error" in updates
        assert "validate_output" in updates["transitions"]


class TestAttachGroundingNode:
    def test_passes_grounding_through_when_present(self):
        grounding = _make_grounding_metadata()
        state = _sample_state()
        state["grounding_metadata"] = grounding
        state["transitions"] = []

        updates = attach_grounding_node(state)

        assert updates["grounding_metadata"] is grounding
        assert "attach_grounding" in updates["transitions"]

    def test_noop_when_grounding_is_none(self):
        state = _sample_state()
        state["grounding_metadata"] = None
        state["transitions"] = []

        updates = attach_grounding_node(state)

        assert updates.get("grounding_metadata") is None
        assert "attach_grounding" in updates["transitions"]


class TestMergeWithScoresNode:
    def test_produces_enriched_payload(self):
        state = _sample_state()
        state["explanations"] = [
            {
                "player_id": "player_1",
                "market_type": "points",
                "recommended_side": "over",
                "confidence_band": "high",
                "rationale": "Strong recent form",
                "risk_flags": [],
            }
        ]
        state["transitions"] = []

        updates = merge_with_scores_node(state)

        assert "result" in updates
        assert "scores" in updates["result"]
        assert updates["result"]["scores"][0].get("llm_rationale") == "Strong recent form"
        assert "merge_with_scores" in updates["transitions"]

    def test_handles_empty_explanations(self):
        state = _sample_state()
        state["explanations"] = []
        state["transitions"] = []

        updates = merge_with_scores_node(state)

        assert "result" in updates
        assert "LLM enrichment applied." in updates["result"]["trace"]["notes"]
