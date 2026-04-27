from __future__ import annotations

from typing import Any

from llm.langchain_enricher import merge_explanations


class SimpleLangGraphFlow:
    """Minimal deterministic flow around prompt/model/parser IO boundaries."""

    def __init__(self, *, prompt_builder, chat_model, structured_parser) -> None:
        self._prompt_builder = prompt_builder
        self._chat_model = chat_model
        self._structured_parser = structured_parser

    def run(self, *, scored_payload: dict[str, Any], match_inputs: dict[str, Any], top_n: int) -> dict[str, Any]:
        state: dict[str, Any] = {
            "scored_payload": scored_payload,
            "match_inputs": match_inputs,
            "top_n": top_n,
            "transitions": [],
        }

        self.prepare_context(state)

        try:
            self.invoke_llm(state)
        except Exception as exc:  # pragma: no cover - explicit fallback behavior validated by tests
            state["error"] = str(exc)
            state["transitions"].append("merge_with_scores")
            return {
                "transitions": state["transitions"],
                "result": _fallback_payload(scored_payload=state["scored_payload"]),
            }

        self.validate_output(state)
        self.merge_with_scores(state)
        return {"transitions": state["transitions"], "result": state["result"]}

    def prepare_context(self, state: dict[str, Any]) -> None:
        state["transitions"].append("prepare_context")
        state["prompt"] = self._prompt_builder(
            scored_payload=state["scored_payload"],
            match_inputs=state["match_inputs"],
            top_n=state["top_n"],
        )

    def invoke_llm(self, state: dict[str, Any]) -> None:
        state["transitions"].append("invoke_llm")
        state["raw_output"] = self._chat_model(state["prompt"])

    def validate_output(self, state: dict[str, Any]) -> None:
        state["transitions"].append("validate_output")
        state["explanations"] = self._structured_parser(state["raw_output"])

    def merge_with_scores(self, state: dict[str, Any]) -> None:
        state["transitions"].append("merge_with_scores")
        state["result"] = merge_explanations(
            scored_payload=state["scored_payload"],
            explanations=state.get("explanations", []),
        )


def _fallback_payload(*, scored_payload: dict[str, Any]) -> dict[str, Any]:
    trace = dict(scored_payload.get("trace") or {})
    notes = list(trace.get("notes", []))
    notes.append("LLM enrichment failed; using deterministic results.")
    trace["notes"] = notes
    return {
        **scored_payload,
        "trace": trace,
    }
