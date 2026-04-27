from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from llm.prompt_builder import build_system_prompt, build_user_prompt
from llm.schema_validation import validate_llm_payload

PromptBuilder = Callable[..., dict[str, str]]
ChatModel = Callable[[dict[str, str]], Any]
StructuredParser = Callable[[Any], list[dict[str, Any]]]


class LangChainEnricher:
    """Composable prompt -> model -> parser chain for deterministic enrichment wiring."""

    def __init__(
        self,
        *,
        prompt_builder: PromptBuilder,
        chat_model: ChatModel,
        structured_parser: StructuredParser,
    ) -> None:
        self._prompt_builder = prompt_builder
        self._chat_model = chat_model
        self._structured_parser = structured_parser

    def enrich(self, *, scored_payload: dict[str, Any], match_inputs: dict[str, Any], top_n: int) -> dict[str, Any]:
        prompt = self._prompt_builder(
            scored_payload=scored_payload,
            match_inputs=match_inputs,
            top_n=top_n,
        )
        model_output = self._chat_model(prompt)
        explanations = self._structured_parser(model_output)
        return merge_explanations(scored_payload=scored_payload, explanations=explanations)


def merge_explanations(*, scored_payload: dict[str, Any], explanations: list[dict[str, Any]]) -> dict[str, Any]:
    explanation_map: dict[str, str] = {}
    for explanation in explanations:
        player_id = str(explanation.get("player_id", "")).strip()
        rationale = str(explanation.get("rationale", "")).strip()
        if player_id and rationale:
            explanation_map[player_id] = rationale

    result = deepcopy(scored_payload)
    result_scores: list[dict[str, Any]] = []
    for score in scored_payload.get("scores", []):
        enriched_score = dict(score)
        rationale = explanation_map.get(str(score.get("player_id", "")))
        if rationale:
            enriched_score["llm_rationale"] = rationale
        result_scores.append(enriched_score)

    trace = dict(result.get("trace") or {})
    notes = list(trace.get("notes", []))
    notes.append("LLM enrichment applied.")
    trace["notes"] = notes

    result["scores"] = result_scores
    result["trace"] = trace
    return result


def default_prompt_builder(*, scored_payload: dict[str, Any], match_inputs: dict[str, Any], top_n: int) -> dict[str, str]:
    return {
        "system": build_system_prompt(),
        "user": build_user_prompt(match_inputs=match_inputs, scored_props=scored_payload.get("scores", []), top_n=top_n),
    }


def default_structured_parser(model_output: Any) -> list[dict[str, Any]]:
    if isinstance(model_output, dict):
        candidates = model_output.get("explanations")
        if not isinstance(candidates, list):
            candidates = [model_output]
    elif isinstance(model_output, list):
        candidates = model_output
    else:
        raise ValueError("model output must be a dictionary or list")

    validated: list[dict[str, Any]] = []
    for candidate in candidates:
        normalized = validate_llm_payload(candidate)
        validated.append(normalized)
    return validated
