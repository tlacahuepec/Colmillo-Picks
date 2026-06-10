"""LangGraph enrichment state schema and graph implementation."""

from __future__ import annotations

from functools import partial
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from llm.client import GroundingMetadataResult
from llm.langchain_enricher import default_prompt_builder, default_structured_parser, merge_explanations


class EnrichmentState(TypedDict, total=False):
    prompt: dict[str, str]
    raw_output: dict[str, Any]
    explanations: list[dict[str, Any]]
    grounding_metadata: GroundingMetadataResult | None
    scored_payload: dict[str, Any]
    match_inputs: dict[str, Any]
    top_n: int
    transitions: list[str]
    error: str | None
    result: dict[str, Any]


def prepare_context_node(state: dict[str, Any]) -> dict[str, Any]:
    prompt = default_prompt_builder(
        scored_payload=state["scored_payload"],
        match_inputs=state["match_inputs"],
        top_n=state["top_n"],
    )
    transitions = list(state.get("transitions", []))
    transitions.append("prepare_context")
    return {"prompt": prompt, "transitions": transitions}


def invoke_llm_node(state: dict[str, Any], *, client: object) -> dict[str, Any]:
    transitions = list(state.get("transitions", []))
    transitions.append("invoke_llm")
    try:
        raw_output = client.generate_structured(
            system_prompt=state["prompt"]["system"],
            user_prompt=state["prompt"]["user"],
            schema={},
        )
    except Exception as exc:
        return {
            "error": str(exc),
            "transitions": transitions,
            "grounding_metadata": None,
        }

    grounding = getattr(client, "last_grounding_metadata", None)
    return {
        "raw_output": raw_output,
        "grounding_metadata": grounding,
        "transitions": transitions,
    }


def validate_output_node(state: dict[str, Any]) -> dict[str, Any]:
    transitions = list(state.get("transitions", []))
    transitions.append("validate_output")
    try:
        explanations = default_structured_parser(state["raw_output"])
    except (ValueError, KeyError) as exc:
        return {"error": str(exc), "transitions": transitions}
    return {"explanations": explanations, "transitions": transitions}


def attach_grounding_node(state: dict[str, Any]) -> dict[str, Any]:
    transitions = list(state.get("transitions", []))
    transitions.append("attach_grounding")
    return {
        "grounding_metadata": state.get("grounding_metadata"),
        "transitions": transitions,
    }


def merge_with_scores_node(state: dict[str, Any]) -> dict[str, Any]:
    transitions = list(state.get("transitions", []))
    transitions.append("merge_with_scores")
    result = merge_explanations(
        scored_payload=state["scored_payload"],
        explanations=state.get("explanations", []),
        grounding=state.get("grounding_metadata"),
    )
    return {"result": result, "transitions": transitions}


def _fallback_payload(*, scored_payload: dict[str, Any]) -> dict[str, Any]:
    trace = dict(scored_payload.get("trace") or {})
    notes = list(trace.get("notes", []))
    notes.append("LLM enrichment failed; using deterministic results.")
    trace["notes"] = notes
    return {**scored_payload, "trace": trace}


def _route_after_invoke_llm(state: dict[str, Any]) -> str:
    if state.get("error"):
        return "fallback_merge"
    return "validate_output"


def _fallback_merge_node(state: dict[str, Any]) -> dict[str, Any]:
    transitions = list(state.get("transitions", []))
    transitions.append("merge_with_scores")
    result = _fallback_payload(scored_payload=state["scored_payload"])
    return {"result": result, "transitions": transitions}


def build_enrichment_graph(*, client: object):
    graph = StateGraph(EnrichmentState)

    graph.add_node("prepare_context", prepare_context_node)
    graph.add_node("invoke_llm", partial(invoke_llm_node, client=client))
    graph.add_node("validate_output", validate_output_node)
    graph.add_node("attach_grounding", attach_grounding_node)
    graph.add_node("merge_with_scores", merge_with_scores_node)
    graph.add_node("fallback_merge", _fallback_merge_node)

    graph.add_edge(START, "prepare_context")
    graph.add_edge("prepare_context", "invoke_llm")
    graph.add_conditional_edges(
        "invoke_llm",
        _route_after_invoke_llm,
        {"validate_output": "validate_output", "fallback_merge": "fallback_merge"},
    )
    graph.add_edge("validate_output", "attach_grounding")
    graph.add_edge("attach_grounding", "merge_with_scores")
    graph.add_edge("merge_with_scores", END)
    graph.add_edge("fallback_merge", END)

    return graph.compile()


def run_enrichment_graph(
    *,
    scored_payload: dict[str, Any],
    match_inputs: dict[str, Any],
    top_n: int,
    client: object,
    include_transitions: bool = False,
) -> dict[str, Any]:
    compiled = build_enrichment_graph(client=client)
    initial_state: dict[str, Any] = {
        "scored_payload": scored_payload,
        "match_inputs": match_inputs,
        "top_n": top_n,
        "transitions": [],
    }
    final_state = compiled.invoke(initial_state)
    result = final_state.get("result", _fallback_payload(scored_payload=scored_payload))
    if include_transitions:
        result["transitions"] = final_state.get("transitions", [])
    return result
