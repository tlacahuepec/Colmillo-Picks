"""Tests for LangGraph StateGraph assembly and compilation (S04, #256)."""

from __future__ import annotations

from unittest.mock import MagicMock

from llm.langgraph_enrichment import build_enrichment_graph, run_enrichment_graph


def _make_mock_client(*, response=None, grounding=None, raises=None):
    client = MagicMock()
    if raises:
        client.generate_structured.side_effect = raises
    else:
        client.generate_structured.return_value = response or {
            "explanations": [
                {
                    "player_id": "player_1",
                    "market_type": "points",
                    "recommended_side": "over",
                    "confidence_band": "high",
                    "rationale": "Strong form",
                    "risk_flags": [],
                }
            ]
        }
    client.last_grounding_metadata = grounding
    return client


def _sample_scored_payload():
    return {
        "scores": [{"player_id": "player_1", "market": "points", "score": 0.8}],
        "trace": {"notes": []},
    }


def _sample_match_inputs():
    return {"home_team": "Lakers", "away_team": "Celtics"}


class TestBuildEnrichmentGraph:
    def test_compiles_without_error(self):
        client = _make_mock_client()
        graph = build_enrichment_graph(client=client)
        assert graph is not None

    def test_compiled_graph_is_invokable(self):
        client = _make_mock_client()
        graph = build_enrichment_graph(client=client)
        assert hasattr(graph, "invoke")


class TestRunEnrichmentGraph:
    def test_happy_path_returns_enriched_payload(self):
        client = _make_mock_client()

        result = run_enrichment_graph(
            scored_payload=_sample_scored_payload(),
            match_inputs=_sample_match_inputs(),
            top_n=5,
            client=client,
        )

        assert "scores" in result
        assert "trace" in result
        assert result["scores"][0].get("llm_rationale") == "Strong form"
        assert "LLM enrichment applied." in result["trace"]["notes"]

    def test_error_path_returns_fallback_payload(self):
        client = _make_mock_client(raises=RuntimeError("API down"))

        result = run_enrichment_graph(
            scored_payload=_sample_scored_payload(),
            match_inputs=_sample_match_inputs(),
            top_n=5,
            client=client,
        )

        assert "scores" in result
        assert "LLM enrichment failed; using deterministic results." in result["trace"]["notes"]

    def test_transitions_recorded_in_happy_path(self):
        client = _make_mock_client()

        result = run_enrichment_graph(
            scored_payload=_sample_scored_payload(),
            match_inputs=_sample_match_inputs(),
            top_n=5,
            client=client,
            include_transitions=True,
        )

        assert "transitions" in result
        assert "prepare_context" in result["transitions"]
        assert "invoke_llm" in result["transitions"]
        assert "merge_with_scores" in result["transitions"]

    def test_multiple_invocations_dont_share_state(self):
        client = _make_mock_client()

        result1 = run_enrichment_graph(
            scored_payload=_sample_scored_payload(),
            match_inputs=_sample_match_inputs(),
            top_n=5,
            client=client,
        )
        result2 = run_enrichment_graph(
            scored_payload=_sample_scored_payload(),
            match_inputs=_sample_match_inputs(),
            top_n=3,
            client=client,
        )

        assert result1["scores"] == result2["scores"]
