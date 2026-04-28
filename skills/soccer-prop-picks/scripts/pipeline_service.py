#!/usr/bin/env python3
"""Application service for soccer pick pipeline orchestration."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable


class PipelineServiceError(RuntimeError):
    """Predictable stage error emitted by the pipeline service."""

    def __init__(self, stage: str):
        self.stage = stage
        super().__init__(f"Pipeline failed during '{self.stage}' stage.")


def _raise_stage_error(stage: str, exc: Exception) -> None:
    raise PipelineServiceError(stage=stage) from exc


def _append_note(trace: dict[str, Any] | None, note: str) -> dict[str, Any]:
    normalized_trace = dict(trace or {})
    notes = list(normalized_trace.get("notes", []))
    notes.append(note)
    normalized_trace["notes"] = notes
    return normalized_trace


def _set_llm_trace_fields(
    trace: dict[str, Any] | None,
    *,
    provider: str,
    model: str,
    latency_ms: int,
    status: str,
    fallback_used: bool,
) -> dict[str, Any]:
    normalized_trace = dict(trace or {})
    normalized_trace["llm_provider"] = provider
    normalized_trace["llm_model"] = model
    normalized_trace["llm_latency_ms"] = latency_ms
    normalized_trace["llm_status"] = status
    normalized_trace["llm_fallback_used"] = fallback_used
    return normalized_trace


def run_pipeline(request: dict[str, Any], deps: dict[str, Callable[..., Any]]) -> str:
    """Run parse → collect → score → [optional llm] → render and return a markdown report."""
    top_n = int(request.get("top_n", 5))
    use_llm = bool(request.get("use_llm", False))
    llm_provider = str(request.get("llm_provider") or "none")
    llm_model = str(request.get("llm_model") or "none")

    try:
        parsed = deps["parse_match_query"](request["match_query"])
    except Exception as exc:  # pragma: no cover - intentionally broad boundary
        _raise_stage_error("parse", exc)

    match_input_request = deps["build_match_input_request"](
        parsed=parsed,
        competition=str(request.get("competition", "League")),
    )

    try:
        match_inputs = deps["collect_inputs"](match_input_request)
    except Exception as exc:  # pragma: no cover - intentionally broad boundary
        _raise_stage_error("collect", exc)

    try:
        scored_payload = deps["score_props"](match_inputs=match_inputs, include_trace=True)
    except Exception as exc:  # pragma: no cover - intentionally broad boundary
        _raise_stage_error("score", exc)

    if use_llm:
        llm_started_at = perf_counter()
        try:
            scored_payload = deps["enrich_with_llm"](
                scored_payload=scored_payload,
                match_inputs=match_inputs,
            )
            llm_latency_ms = max(0, round((perf_counter() - llm_started_at) * 1000))
            scored_payload = dict(scored_payload)
            scored_payload["trace"] = _set_llm_trace_fields(
                scored_payload.get("trace"),
                provider=llm_provider,
                model=llm_model,
                latency_ms=llm_latency_ms,
                status="success",
                fallback_used=False,
            )
        except Exception:
            llm_latency_ms = max(0, round((perf_counter() - llm_started_at) * 1000))
            scored_payload = dict(scored_payload)
            trace_with_note = _append_note(
                scored_payload.get("trace"),
                "LLM enrichment failed; using deterministic results.",
            )
            scored_payload["trace"] = _set_llm_trace_fields(
                trace_with_note,
                provider=llm_provider,
                model=llm_model,
                latency_ms=llm_latency_ms,
                status="failed",
                fallback_used=True,
            )
    else:
        scored_payload = dict(scored_payload)
        scored_payload["trace"] = _set_llm_trace_fields(
            scored_payload.get("trace"),
            provider=llm_provider,
            model=llm_model,
            latency_ms=0,
            status="not_requested",
            fallback_used=False,
        )

    return deps["render_report"](
        scored_props=scored_payload["scores"],
        match_inputs=match_inputs,
        availability_data=request.get("availability_data", {}),
        top_n=top_n,
        trace=scored_payload.get("trace"),
    )
