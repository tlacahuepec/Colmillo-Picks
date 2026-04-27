#!/usr/bin/env python3
"""Application service for soccer pick pipeline orchestration."""

from __future__ import annotations

from typing import Any, Callable


class PipelineServiceError(RuntimeError):
    """Predictable stage error emitted by the pipeline service."""

    def __init__(self, stage: str):
        self.stage = stage
        super().__init__(f"Pipeline failed during '{self.stage}' stage.")


def _raise_stage_error(stage: str, exc: Exception) -> None:
    raise PipelineServiceError(stage=stage) from exc


def run_pipeline(request: dict[str, Any], deps: dict[str, Callable[..., Any]]) -> str:
    """Run parse → collect → score → render and return a markdown report."""
    top_n = int(request.get("top_n", 5))

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

    return deps["render_report"](
        scored_props=scored_payload["scores"],
        match_inputs=match_inputs,
        availability_data=request.get("availability_data", {}),
        top_n=top_n,
        trace=scored_payload.get("trace"),
    )
