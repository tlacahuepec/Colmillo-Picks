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
    return run_pipeline_with_payload(request, deps)["report_markdown"]


def run_pipeline_with_payload(
    request: dict[str, Any], deps: dict[str, Callable[..., Any]]
) -> dict[str, Any]:
    """Same orchestration as ``run_pipeline`` but returns the structured payload.

    Returned dict contains:
      - ``report_markdown``: the rendered markdown report.
      - ``scores``: scored picks list as produced by ``score_props``.
      - ``trace``: scoring/LLM trace including ``llm_status`` and latency.
      - ``match_inputs``: the collected match-input payload.
      - ``steps``: list of stage timing dicts with name, status, and duration_ms.
    """
    top_n = int(request.get("top_n", 5))
    use_llm = bool(request.get("use_llm", False))
    llm_provider = str(request.get("llm_provider") or ("gemini" if use_llm else "none"))
    llm_model = str(request.get("llm_model") or ("gemini-2.5-flash" if use_llm else "none"))

    steps: list[dict[str, Any]] = []

    t0 = perf_counter()
    try:
        parsed = deps["parse_match_query"](request["match_query"])
    except Exception as exc:  # pragma: no cover - intentionally broad boundary
        steps.append({"name": "parse", "status": "failed", "duration_ms": max(0, round((perf_counter() - t0) * 1000))})
        _raise_stage_error("parse", exc)
    steps.append({"name": "parse", "status": "success", "duration_ms": max(0, round((perf_counter() - t0) * 1000))})

    match_input_request = deps["build_match_input_request"](
        parsed=parsed,
        competition=str(request.get("competition", "League")),
    )

    t0 = perf_counter()
    try:
        match_inputs = deps["collect_inputs"](match_input_request)
    except Exception as exc:  # pragma: no cover - intentionally broad boundary
        steps.append({"name": "collect", "status": "failed", "duration_ms": max(0, round((perf_counter() - t0) * 1000))})
        _raise_stage_error("collect", exc)
    steps.append({"name": "collect", "status": "success", "duration_ms": max(0, round((perf_counter() - t0) * 1000))})

    t0 = perf_counter()
    try:
        scored_payload = deps["score_props"](match_inputs=match_inputs, include_trace=True)
    except Exception as exc:  # pragma: no cover - intentionally broad boundary
        steps.append({"name": "score", "status": "failed", "duration_ms": max(0, round((perf_counter() - t0) * 1000))})
        _raise_stage_error("score", exc)
    steps.append({"name": "score", "status": "success", "duration_ms": max(0, round((perf_counter() - t0) * 1000))})

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
            steps.append({"name": "llm_enrichment", "status": "success", "duration_ms": llm_latency_ms})
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
            steps.append({"name": "llm_enrichment", "status": "failed", "duration_ms": llm_latency_ms})
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

    t0 = perf_counter()
    availability_data: dict[str, Any] = {}
    check_availability = deps.get("check_availability")
    if check_availability is not None:
        try:
            pick_list = [
                {"player_id": p.get("player_id", ""), "market": p.get("market", "")}
                for p in scored_payload["scores"][:top_n]
            ]
            availability_data = check_availability(pick_list)
            steps.append({"name": "availability", "status": "success", "duration_ms": max(0, round((perf_counter() - t0) * 1000))})
        except Exception:
            steps.append({"name": "availability", "status": "failed", "duration_ms": max(0, round((perf_counter() - t0) * 1000))})

    t0 = perf_counter()
    report_markdown = deps["render_report"](
        scored_props=scored_payload["scores"],
        match_inputs=match_inputs,
        availability_data=availability_data,
        top_n=top_n,
        trace=scored_payload.get("trace"),
    )
    steps.append({"name": "render", "status": "success", "duration_ms": max(0, round((perf_counter() - t0) * 1000))})

    return {
        "report_markdown": report_markdown,
        "scores": scored_payload["scores"],
        "trace": scored_payload.get("trace"),
        "match_inputs": match_inputs,
        "steps": steps,
    }
