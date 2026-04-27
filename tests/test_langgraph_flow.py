from __future__ import annotations

from tests.conftest import load_script_module


def test_langgraph_flow_runs_nodes_in_order() -> None:
    module = load_script_module("llm/langgraph_flow.py")

    flow = module.SimpleLangGraphFlow(
        prompt_builder=lambda **_: {"system": "S", "user": "U"},
        chat_model=lambda _: {"raw": "json"},
        structured_parser=lambda _: [{"player_id": "p1", "rationale": "Strong role"}],
    )

    result = flow.run(
        scored_payload={"scores": [{"player_id": "p1"}], "trace": {}},
        match_inputs={"match_id": "M1"},
        top_n=2,
    )

    assert result["transitions"] == [
        "prepare_context",
        "invoke_llm",
        "validate_output",
        "merge_with_scores",
    ]
    assert result["result"]["scores"][0]["llm_rationale"] == "Strong role"


def test_langgraph_flow_fallback_path_on_error() -> None:
    module = load_script_module("llm/langgraph_flow.py")

    flow = module.SimpleLangGraphFlow(
        prompt_builder=lambda **_: {"system": "S", "user": "U"},
        chat_model=lambda _: (_ for _ in ()).throw(RuntimeError("provider down")),
        structured_parser=lambda _: [],
    )

    payload = {"scores": [{"player_id": "p1"}], "trace": {"notes": []}}
    result = flow.run(scored_payload=payload, match_inputs={"match_id": "M1"}, top_n=1)

    assert result["transitions"] == ["prepare_context", "invoke_llm", "merge_with_scores"]
    assert result["result"]["scores"] == payload["scores"]
    assert result["result"]["trace"]["notes"][-1] == "LLM enrichment failed; using deterministic results."
