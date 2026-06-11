"""End-to-end integration tests for LangGraph enrichment with toggle (S08, #260)."""

from __future__ import annotations

from copy import deepcopy

from llm.client import GroundingMetadataResult, GroundingSource, GroundingSupport
from llm.provider_adapter import build_enrich_with_llm


class _MockGroundingClient:
    """Mock client that returns valid schema output and grounding metadata."""

    def __init__(self) -> None:
        self.last_grounding_metadata = GroundingMetadataResult(
            sources=(
                GroundingSource(url="https://stats.nba.com/player/1", title="NBA Stats"),
                GroundingSource(url="https://espn.com/nba", title="ESPN NBA"),
            ),
            supports=(
                GroundingSupport(
                    start_index=0, end_index=50, text="averaging 25.3 points", source_indices=(0,)
                ),
            ),
            web_search_queries=("player points average 2026",),
        )

    def generate_structured(
        self, *, system_prompt: str, user_prompt: str, schema: dict, temperature: float | None = None
    ) -> dict:
        return {
            "explanations": [
                {
                    "player_id": "lebron_james",
                    "market_type": "points",
                    "recommended_side": "over",
                    "confidence_band": "high",
                    "rationale": "Averaging 25.3 points with strong recent form",
                    "risk_flags": ["back_to_back"],
                }
            ]
        }


class _MockFailingClient:
    """Mock client that raises on generate_structured."""

    last_grounding_metadata = None

    def generate_structured(self, **kwargs) -> dict:
        raise RuntimeError("Simulated API failure")


def _sample_scored_payload():
    return {
        "scores": [
            {
                "player_id": "lebron_james",
                "player_name": "LeBron James",
                "market": "points",
                "score": 0.85,
            }
        ],
        "trace": {"notes": []},
    }


def _sample_match_inputs():
    return {
        "home_team": "Lakers",
        "away_team": "Celtics",
        "match_date": "2026-06-09",
        "league": "NBA",
    }


class TestLangGraphIntegrationHappyPath:
    def test_toggle_on_returns_enriched_payload_with_grounding(self, monkeypatch):
        monkeypatch.setattr(
            "llm.provider_adapter.DeterministicMockLLMClient",
            _MockGroundingClient,
        )
        env = {"COLMILLO_USE_LANGGRAPH": "true"}

        fn = build_enrich_with_llm(
            use_llm=False,
            llm_provider=None,
            llm_model=None,
            getenv=env.get,
        )

        result = fn(
            scored_payload=_sample_scored_payload(),
            match_inputs=_sample_match_inputs(),
        )

        assert "scores" in result
        assert "trace" in result
        assert result["scores"][0]["llm_rationale"] == "Averaging 25.3 points with strong recent form"
        assert "LLM enrichment applied." in result["trace"]["notes"]
        assert result["trace"]["grounding_sources"] == [
            {"url": "https://stats.nba.com/player/1", "title": "NBA Stats"},
            {"url": "https://espn.com/nba", "title": "ESPN NBA"},
        ]
        assert result["trace"]["web_search_queries"] == ["player points average 2026"]
        assert result["trace"]["grounding_supports_count"] == 1

    def test_toggle_on_preserves_original_score_fields(self, monkeypatch):
        monkeypatch.setattr(
            "llm.provider_adapter.DeterministicMockLLMClient",
            _MockGroundingClient,
        )
        env = {"COLMILLO_USE_LANGGRAPH": "true"}

        fn = build_enrich_with_llm(
            use_llm=False,
            llm_provider=None,
            llm_model=None,
            getenv=env.get,
        )

        payload = _sample_scored_payload()
        result = fn(scored_payload=deepcopy(payload), match_inputs=_sample_match_inputs())

        assert result["scores"][0]["player_id"] == "lebron_james"
        assert result["scores"][0]["score"] == 0.85


class _MockValidClientNoGrounding:
    """Mock client with valid schema output but no grounding metadata."""

    last_grounding_metadata = None

    def generate_structured(self, **kwargs) -> dict:
        return {
            "explanations": [
                {
                    "player_id": "lebron_james",
                    "market_type": "points",
                    "recommended_side": "over",
                    "confidence_band": "medium",
                    "rationale": "Standard pick from non-grounded path",
                    "risk_flags": [],
                }
            ]
        }


class TestLangGraphIntegrationToggleOff:
    def test_toggle_off_no_grounding_keys_in_trace(self, monkeypatch):
        monkeypatch.setattr(
            "llm.provider_adapter.DeterministicMockLLMClient",
            _MockValidClientNoGrounding,
        )
        env = {"COLMILLO_USE_LANGGRAPH": "false"}

        fn = build_enrich_with_llm(
            use_llm=False,
            llm_provider=None,
            llm_model=None,
            getenv=env.get,
        )

        result = fn(
            scored_payload=_sample_scored_payload(),
            match_inputs=_sample_match_inputs(),
        )

        assert isinstance(result, dict)
        assert "grounding_sources" not in result.get("trace", {})
        assert "web_search_queries" not in result.get("trace", {})


class TestLangGraphIntegrationErrorFallback:
    def test_graph_handles_llm_failure_gracefully(self, monkeypatch):
        monkeypatch.setattr(
            "llm.provider_adapter.DeterministicMockLLMClient",
            _MockFailingClient,
        )
        env = {"COLMILLO_USE_LANGGRAPH": "true"}

        fn = build_enrich_with_llm(
            use_llm=False,
            llm_provider=None,
            llm_model=None,
            getenv=env.get,
        )

        result = fn(
            scored_payload=_sample_scored_payload(),
            match_inputs=_sample_match_inputs(),
        )

        assert "scores" in result
        assert "trace" in result
        assert "LLM enrichment failed; using deterministic results." in result["trace"]["notes"]
