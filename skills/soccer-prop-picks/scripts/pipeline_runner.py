"""Shared multi-sport pipeline runner.

Executes any registered SportModule through a common sequence:
collect → score → rank. No sport-specific branching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from pick_request import PickRequest
from sport_module import SportModule


class PipelineRunError(RuntimeError):
    def __init__(self, stage: str, message: str, error_details: dict[str, Any] | None = None):
        self.stage = stage
        self.message = message
        self.error_details = error_details
        super().__init__(f"Pipeline failed at '{stage}': {message}")


@dataclass
class PipelineResult:
    status: str = "success"
    scores: list[dict[str, Any]] = field(default_factory=list)
    match_inputs: dict[str, Any] = field(default_factory=dict)
    steps: list[dict[str, Any]] = field(default_factory=list)


class PipelineRunner:
    def run(self, *, request: PickRequest, module: SportModule) -> PipelineResult:
        steps: list[dict[str, Any]] = []

        t0 = perf_counter()
        try:
            match_inputs = module.collect_inputs(
                home_team=request.home_team,
                away_team=request.away_team,
                match_date=request.event_date,
                league=request.league,
            )
        except Exception as exc:
            steps.append({"name": "collect", "status": "failed", "duration_ms": _elapsed(t0)})
            error_details = {"reason": exc.reason, "sport": getattr(module, "sport_id", None)} if hasattr(exc, "reason") else None
            raise PipelineRunError(stage="collect", message=str(exc), error_details=error_details) from exc
        steps.append({"name": "collect", "status": "success", "duration_ms": _elapsed(t0)})

        t0 = perf_counter()
        try:
            scores = module.score(match_inputs, markets=request.markets)
        except Exception as exc:
            steps.append({"name": "score", "status": "failed", "duration_ms": _elapsed(t0)})
            error_details = {"reason": exc.reason, "sport": getattr(module, "sport_id", None)} if hasattr(exc, "reason") else None
            raise PipelineRunError(stage="score", message=str(exc), error_details=error_details) from exc
        steps.append({"name": "score", "status": "success", "duration_ms": _elapsed(t0)})

        ranked = sorted(scores, key=lambda s: s.get("score", 0), reverse=True)
        ranked = ranked[: request.top_n]

        return PipelineResult(
            status="success",
            scores=ranked,
            match_inputs=match_inputs,
            steps=steps,
        )


def _elapsed(t0: float) -> int:
    return max(0, round((perf_counter() - t0) * 1000))
