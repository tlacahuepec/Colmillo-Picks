"""Slate orchestration: discovers matches, runs pipelines, normalizes and ranks."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from baseball_module import BaseballDataQualityError
from slate_ranking import SlateCandidate, candidates_from_picks, rank_slate_candidates


@dataclass(frozen=True, slots=True)
class SlateResult:
    candidates: list[SlateCandidate]
    match_runs: list[dict[str, Any]]
    latency_ms: int
    discovery_latency_ms: int
    matches_attempted: int
    matches_succeeded: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class SlateOrchestrationDeps:
    discover_matches: Callable[..., dict[str, Any]]
    run_match_pipeline: Callable[..., list[dict[str, Any]]]
    get_token_usage: Callable[[], tuple[int, int, int]] | None = None


def execute_slate_job(
    *,
    request_dict: dict[str, Any],
    deps: SlateOrchestrationDeps,
) -> SlateResult:
    t0 = time.perf_counter()

    date = request_dict["date"]
    sports = request_dict.get("sports", ["soccer", "basketball", "baseball"])
    max_matches_per_sport = request_dict.get("max_matches_per_sport", 3)
    top_n = request_dict.get("top_n", 10)

    t_discovery = time.perf_counter()
    discovery_result = deps.discover_matches(
        date_utc=date,
        sports=sports,
        limit_per_sport=max_matches_per_sport,
    )
    discovery_latency_ms = max(0, round((time.perf_counter() - t_discovery) * 1000))

    all_candidates: list[SlateCandidate] = []
    match_runs: list[dict[str, Any]] = []
    matches_attempted = 0
    matches_succeeded = 0

    results = discovery_result.get("results", {})
    for sport, sport_data in results.items():
        if not isinstance(sport_data, dict):
            continue
        matches = sport_data.get("matches", [])
        for match in matches:
            if not isinstance(match, dict):
                continue
            home_team = match.get("home_team", "Unknown")
            away_team = match.get("away_team", "Unknown")
            event_date = match.get("event_date", date)
            matches_attempted += 1

            t_match = time.perf_counter()
            try:
                scores = deps.run_match_pipeline(
                    sport=sport,
                    home_team=home_team,
                    away_team=away_team,
                    event_date=event_date,
                    markets=(),
                )
                match_latency_ms = max(0, round((time.perf_counter() - t_match) * 1000))
                matches_succeeded += 1

                candidates = candidates_from_picks(
                    scores,
                    sport=sport,
                    source_match=match,
                )
                all_candidates.extend(candidates)

                match_runs.append({
                    "sport": sport,
                    "home_team": home_team,
                    "away_team": away_team,
                    "event_date": event_date,
                    "status": "success",
                    "error_stage": None,
                    "error_message": None,
                    "pick_count": len(candidates),
                    "latency_ms": match_latency_ms,
                })
            except BaseballDataQualityError as exc:
                match_latency_ms = max(0, round((time.perf_counter() - t_match) * 1000))
                status = "pending_data" if exc.reason == "hitter_inputs_unavailable" else "failed"
                match_runs.append({
                    "sport": sport,
                    "home_team": home_team,
                    "away_team": away_team,
                    "event_date": event_date,
                    "status": status,
                    "error_stage": "scoring",
                    "error_message": str(exc)[:500],
                    "pick_count": 0,
                    "latency_ms": match_latency_ms,
                })
            except Exception as exc:
                match_latency_ms = max(0, round((time.perf_counter() - t_match) * 1000))
                match_runs.append({
                    "sport": sport,
                    "home_team": home_team,
                    "away_team": away_team,
                    "event_date": event_date,
                    "status": "failed",
                    "error_stage": "pipeline",
                    "error_message": str(exc)[:500],
                    "pick_count": 0,
                    "latency_ms": match_latency_ms,
                })

    ranked = rank_slate_candidates(all_candidates, top_n=top_n)
    total_latency_ms = max(0, round((time.perf_counter() - t0) * 1000))

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    if deps.get_token_usage:
        p, c, t = deps.get_token_usage()
        if t > 0:
            prompt_tokens = p
            completion_tokens = c
            total_tokens = t

    return SlateResult(
        candidates=ranked,
        match_runs=match_runs,
        latency_ms=total_latency_ms,
        discovery_latency_ms=discovery_latency_ms,
        matches_attempted=matches_attempted,
        matches_succeeded=matches_succeeded,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
