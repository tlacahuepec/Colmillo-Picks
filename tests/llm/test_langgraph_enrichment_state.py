"""Tests for the LangGraph enrichment state schema (S02, #254)."""

from __future__ import annotations

from typing import get_type_hints

from langgraph.graph import StateGraph

from llm.langgraph_enrichment import EnrichmentState


class TestEnrichmentStateTypedDict:
    """Verify EnrichmentState is a valid TypedDict compatible with LangGraph."""

    def test_is_valid_typed_dict_with_all_fields(self):
        state: EnrichmentState = {
            "prompt": {"system": "sys", "user": "usr"},
            "raw_output": {"key": "value"},
            "explanations": [{"player_id": "p1", "rationale": "reason"}],
            "grounding_metadata": None,
            "scored_payload": {"scores": []},
            "match_inputs": {"home_team": "A", "away_team": "B"},
            "top_n": 5,
            "transitions": ["node_a", "node_b"],
            "error": None,
        }
        assert state["top_n"] == 5
        assert state["error"] is None

    def test_partial_construction_with_required_inputs_only(self):
        state: EnrichmentState = {
            "scored_payload": {"scores": []},
            "match_inputs": {"home_team": "A", "away_team": "B"},
            "top_n": 5,
        }
        assert "prompt" not in state
        assert state["top_n"] == 5

    def test_has_expected_field_names(self):
        hints = get_type_hints(EnrichmentState)
        expected_fields = {
            "prompt",
            "raw_output",
            "explanations",
            "grounding_metadata",
            "scored_payload",
            "match_inputs",
            "top_n",
            "transitions",
            "error",
        }
        assert set(hints.keys()) == expected_fields

    def test_compatible_with_langgraph_state_graph(self):
        graph = StateGraph(EnrichmentState)
        assert graph is not None
