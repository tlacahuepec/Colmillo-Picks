"""Shared multi-sport pipeline runner.

Executes any registered SportModule through a common sequence:
collect → score → rank. No sport-specific branching.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from pick_request import PickRequest
from sport_module import SportModule

_MAX_PICKS_PER_PLAYER = 3
_MIN_PICKS_PER_TEAM = 3
_DIVERSITY_SPORTS = {"basketball"}


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

        if request.sport in _DIVERSITY_SPORTS:
            ranked = _apply_pick_diversity(ranked, request.top_n, match_inputs)
        else:
            ranked = ranked[: request.top_n]

        return PipelineResult(
            status="success",
            scores=ranked,
            match_inputs=match_inputs,
            steps=steps,
        )


def _elapsed(t0: float) -> int:
    return max(0, round((perf_counter() - t0) * 1000))


def _apply_pick_diversity(
    ranked: list[dict[str, Any]],
    top_n: int,
    match_inputs: dict[str, Any],
) -> list[dict[str, Any]]:
    """Select top picks with per-player cap and team balance guarantee."""
    home_team = match_inputs.get("home_team", "")
    away_team = match_inputs.get("away_team", "")

    home_codes = _team_identifiers(home_team)
    away_codes = _team_identifiers(away_team)

    selected: list[dict[str, Any]] = []
    player_counts: Counter[str] = Counter()

    remaining: list[dict[str, Any]] = []

    for pick in ranked:
        player = pick.get("player", "")
        if player_counts[player] >= _MAX_PICKS_PER_PLAYER:
            remaining.append(pick)
            continue
        if len(selected) >= top_n:
            remaining.append(pick)
            continue
        selected.append(pick)
        player_counts[player] += 1

    home_count = sum(1 for s in selected if _is_team(s, home_codes))
    away_count = sum(1 for s in selected if _is_team(s, away_codes))

    if away_count < _MIN_PICKS_PER_TEAM and len(selected) >= top_n:
        needed = _MIN_PICKS_PER_TEAM - away_count
        _swap_in_team_picks(selected, remaining, away_codes, needed, player_counts)
    elif home_count < _MIN_PICKS_PER_TEAM and len(selected) >= top_n:
        needed = _MIN_PICKS_PER_TEAM - home_count
        _swap_in_team_picks(selected, remaining, home_codes, needed, player_counts)

    return selected[:top_n]


def _swap_in_team_picks(
    selected: list[dict[str, Any]],
    remaining: list[dict[str, Any]],
    team_codes: set[str],
    needed: int,
    player_counts: Counter[str],
) -> None:
    candidates = [
        p for p in remaining
        if _is_team(p, team_codes) and player_counts[p.get("player", "")] < _MAX_PICKS_PER_PLAYER
    ]
    if not candidates:
        return

    for candidate in candidates[:needed]:
        for i in range(len(selected) - 1, -1, -1):
            if not _is_team(selected[i], team_codes):
                evicted = selected.pop(i)
                player_counts[evicted.get("player", "")] -= 1
                selected.append(candidate)
                player_counts[candidate.get("player", "")] += 1
                remaining.remove(candidate)
                break


def _is_team(pick: dict[str, Any], team_codes: set[str]) -> bool:
    pick_team = str(pick.get("team", "")).upper()
    return pick_team in team_codes


def _team_identifiers(team_name: str) -> set[str]:
    """Build a set of possible team codes/names for matching."""
    codes: set[str] = set()
    if team_name:
        codes.add(team_name.upper())
        codes.add(team_name[:3].upper())
    return codes
