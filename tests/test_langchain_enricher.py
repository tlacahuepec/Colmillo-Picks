from __future__ import annotations

from tests.conftest import load_script_module


def test_enrich_with_chain_invokes_prompt_model_and_parser_in_order() -> None:
    module = load_script_module("llm/langchain_enricher.py")
    calls: list[str] = []

    def prompt_builder(*, match_inputs, scored_payload, top_n):
        calls.append("prompt")
        assert match_inputs == {"match_id": "M1"}
        assert scored_payload == {"scores": [{"player_id": "p1"}], "trace": {"notes": []}}
        assert top_n == 3
        return {"system": "S", "user": "U"}

    def chat_model(prompt):
        calls.append("model")
        assert prompt == {"system": "S", "user": "U"}
        return {"raw": "json"}

    def structured_parser(model_output):
        calls.append("parser")
        assert model_output == {"raw": "json"}
        return [{"player_id": "p1", "rationale": "Good edge"}]

    enricher = module.LangChainEnricher(
        prompt_builder=prompt_builder,
        chat_model=chat_model,
        structured_parser=structured_parser,
    )

    result = enricher.enrich(
        scored_payload={"scores": [{"player_id": "p1"}], "trace": {"notes": []}},
        match_inputs={"match_id": "M1"},
        top_n=3,
    )

    assert calls == ["prompt", "model", "parser"]
    assert result["scores"][0]["llm_rationale"] == "Good edge"
    assert result["trace"]["notes"][-1] == "LLM enrichment applied."


def test_enrich_with_chain_keeps_original_scores_when_no_explanations_match() -> None:
    module = load_script_module("llm/langchain_enricher.py")

    enricher = module.LangChainEnricher(
        prompt_builder=lambda **_: {"system": "S", "user": "U"},
        chat_model=lambda _: {"raw": "json"},
        structured_parser=lambda _: [{"player_id": "other", "rationale": "No match"}],
    )

    payload = {"scores": [{"player_id": "p1", "player_name": "A"}], "trace": {}}
    result = enricher.enrich(scored_payload=payload, match_inputs={"match_id": "M1"}, top_n=1)

    assert result["scores"][0]["player_name"] == "A"
    assert "llm_rationale" not in result["scores"][0]
