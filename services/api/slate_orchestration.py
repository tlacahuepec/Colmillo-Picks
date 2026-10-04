"""Slate orchestration: discovers matches, runs pipelines, normalizes and ranks."""

from __future__ import annotations

import time
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone as utc_timezone
from typing import Any, Callable

from baseball_module import BaseballDataQualityError
from nfl_module import NflDataQualityError, NflNoPicks
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
    discovery_failures: int = 0
    discovered_matches: list[dict[str, Any]] | None = None
    interrupted: bool = False
    stop_reason: str | None = None


@dataclass(frozen=True, slots=True)
class SlateOrchestrationDeps:
    discover_matches: Callable[..., dict[str, Any]]
    run_match_pipeline: Callable[..., list[dict[str, Any]]]
    get_token_usage: Callable[[], tuple[int, int, int]] | None = None
    read_catalog: Callable[..., Any] | None = None
    match_operation: Callable[..., Any] | None = None


def execute_slate_job(
    *,
    request_dict: dict[str, Any],
    deps: SlateOrchestrationDeps,
    on_checkpoint: Callable[[str, list[dict[str, Any]], list[SlateCandidate], list[dict[str, Any]], int], None] | None = None,
    total_budget_seconds: float = 600,
    per_match_budget_seconds: float = 120,
    discovery_override: list[dict[str, Any]] | None = None,
    existing_match_runs: list[dict[str, Any]] | None = None,
    existing_candidates: list[SlateCandidate] | None = None,
) -> SlateResult:
    t0 = time.perf_counter()

    date = request_dict["date"]
    sports = request_dict.get("sports", ["soccer", "basketball", "baseball", "nfl"])
    max_matches_per_sport = request_dict.get("max_matches_per_sport", 3)
    top_n = request_dict.get("top_n", 10)
    timezone = request_dict.get("timezone")

    if discovery_override is None:
        t_discovery = time.perf_counter()
        discovery_result = deps.discover_matches(
            date_utc=date, sports=sports, limit_per_sport=max_matches_per_sport, timezone=timezone,
        )
        discovery_latency_ms = max(0, round((time.perf_counter() - t_discovery) * 1000))
        results = discovery_result.get("results", {})
    else:
        discovery_latency_ms = 0
        results: dict[str, dict[str, Any]] = {}
        for item in discovery_override:
            if isinstance(item, dict) and isinstance(item.get("match"), dict):
                results.setdefault(str(item.get("sport", "")), {"matches": []})["matches"].append(item["match"])

    all_candidates: list[SlateCandidate] = list(existing_candidates or [])
    match_runs: list[dict[str, Any]] = list(existing_match_runs or [])
    discovered_matches = [
        {"sport": sport, "match": match}
        for sport, sport_data in results.items()
        if isinstance(sport_data, dict)
        for match in sport_data.get("matches", [])
        if isinstance(match, dict)
    ]
    if on_checkpoint:
        on_checkpoint("matches", discovered_matches, all_candidates, match_runs, discovery_latency_ms)
    for sport, sport_data in results.items():
        if not isinstance(sport_data, dict):
            continue
        matches = sport_data.get("matches", [])
        for match in matches:
            if not isinstance(match, dict):
                continue
            if any(
                run.get("sport") == sport and run.get("home_team") == match.get("home_team")
                and run.get("away_team") == match.get("away_team") and run.get("event_date") == match.get("event_date", date)
                for run in match_runs
            ):
                continue
            if time.perf_counter() - t0 >= total_budget_seconds:
                return _interrupted_result(
                    all_candidates, match_runs, t0, discovery_latency_ms, results, discovered_matches,
                    deps, top_n, "budget_exhausted"
                )
            home_team = match.get("home_team", "Unknown")
            away_team = match.get("away_team", "Unknown")
            event_date = match.get("event_date", date)
            t_match = time.perf_counter()
            match_run, candidates = _execute_slate_match(
                deps=deps, sport=sport, home_team=home_team, away_team=away_team,
                event_date=event_date, source_match=match,
            )
            all_candidates.extend(candidates)
            match_runs.append(match_run)
            if on_checkpoint:
                on_checkpoint("matches", discovered_matches, all_candidates, match_runs, discovery_latency_ms)
            if (
                time.perf_counter() - t0 >= total_budget_seconds
                or time.perf_counter() - t_match > per_match_budget_seconds
            ):
                return _interrupted_result(
                    all_candidates, match_runs, t0, discovery_latency_ms, results, discovered_matches,
                    deps, top_n, "budget_exhausted"
                )

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
        discovery_failures=sum(bool(v.get("error")) for v in results.values() if isinstance(v, dict)),
        candidates=ranked,
        match_runs=match_runs,
        latency_ms=total_latency_ms,
        discovery_latency_ms=discovery_latency_ms,
        matches_attempted=len(match_runs),
        matches_succeeded=sum(run.get("status") == "success" for run in match_runs),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        discovered_matches=discovered_matches,
    )


def _execute_slate_match(
    *, deps: SlateOrchestrationDeps, sport: str, home_team: str, away_team: str,
    event_date: str, source_match: dict[str, Any],
) -> tuple[dict[str, Any], list[SlateCandidate]]:
    """Run one sequential match attempt and retain its child diagnostic identity."""
    t_match = time.perf_counter()
    context = (
        deps.match_operation(sport=sport, home_team=home_team, away_team=away_team, event_date=event_date)
        if deps.match_operation else nullcontext(None)
    )
    with context as diagnostic:
        operation_id = getattr(diagnostic, "id", None)
        candidates: list[SlateCandidate] = []
        try:
            catalog_read = None
            if deps.read_catalog:
                catalog_read = deps.read_catalog(
                    sport=sport, home_team=home_team, away_team=away_team,
                    event_date=event_date, now=datetime.now(utc_timezone.utc),
                )
            scores = deps.run_match_pipeline(
                sport=sport, home_team=home_team, away_team=away_team,
                event_date=event_date, markets=(),
            )
            candidates = candidates_from_picks(
                scores,
                sport=sport,
                source_match={**source_match, **({"catalog_source": catalog_read.source,
                                                   "catalog_refresh_resources": list(catalog_read.refresh_resources)}
                                                  if catalog_read else {})},
            )
            match_run = {
                "sport": sport, "home_team": home_team, "away_team": away_team,
                "event_date": event_date, "status": "success", "error_stage": None,
                "error_message": None, "pick_count": len(candidates),
                "latency_ms": max(0, round((time.perf_counter() - t_match) * 1000)),
                "catalog_source": catalog_read.source if catalog_read else None,
                "catalog_refresh_resources": list(catalog_read.refresh_resources) if catalog_read else [],
            }
        except NflNoPicks as exc:
            match_run = {
                "sport": sport, "home_team": home_team, "away_team": away_team,
                "event_date": event_date, "status": "no_picks", "error_stage": None,
                "error_message": str(exc)[:500], "pick_count": 0,
                "latency_ms": max(0, round((time.perf_counter() - t_match) * 1000)),
            }
        except NflDataQualityError as exc:
            summary = exc.reason.get("recommendation_summary", {}) if isinstance(exc.reason, dict) else {}
            match_run = {
                "sport": sport, "home_team": home_team, "away_team": away_team,
                "event_date": event_date, "status": "failed", "error_stage": "offers",
                "error_message": summary.get("message") or str(exc)[:500], "pick_count": 0,
                "latency_ms": max(0, round((time.perf_counter() - t_match) * 1000)),
                "recommendation_summary": summary,
            }
        except BaseballDataQualityError as exc:
            status = "pending_data" if exc.reason == "hitter_inputs_unavailable" else "failed"
            match_run = {
                "sport": sport, "home_team": home_team, "away_team": away_team,
                "event_date": event_date, "status": status, "error_stage": "scoring",
                "error_message": str(exc)[:500], "pick_count": 0,
                "latency_ms": max(0, round((time.perf_counter() - t_match) * 1000)),
            }
        except Exception as exc:
            match_run = {
                "sport": sport, "home_team": home_team, "away_team": away_team,
                "event_date": event_date, "status": "failed", "error_stage": "pipeline",
                "error_message": str(exc)[:500], "pick_count": 0,
                "latency_ms": max(0, round((time.perf_counter() - t_match) * 1000)),
            }

        if diagnostic:
            outcome = {"success": "success", "no_picks": "no_picks", "pending_data": "partial"}.get(
                match_run["status"], "failed"
            )
            diagnostic.finish(outcome, pick_count=match_run["pick_count"])
        if operation_id:
            match_run["operation_id"] = operation_id
        return match_run, candidates


def _interrupted_result(
    candidates: list[SlateCandidate], match_runs: list[dict[str, Any]], started: float,
    discovery_latency_ms: int, results: dict[str, Any], discovered_matches: list[dict[str, Any]],
    deps: SlateOrchestrationDeps, top_n: int, reason: str,
) -> SlateResult:
    prompt_tokens = completion_tokens = total_tokens = None
    if deps.get_token_usage:
        prompt, completion, total = deps.get_token_usage()
        if total > 0:
            prompt_tokens, completion_tokens, total_tokens = prompt, completion, total
    return SlateResult(
        candidates=rank_slate_candidates(candidates, top_n=top_n), match_runs=match_runs,
        latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
        discovery_latency_ms=discovery_latency_ms, matches_attempted=len(match_runs),
        matches_succeeded=sum(run.get("status") == "success" for run in match_runs),
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total_tokens,
        discovery_failures=sum(bool(v.get("error")) for v in results.values() if isinstance(v, dict)),
        discovered_matches=discovered_matches, interrupted=True, stop_reason=reason,
    )
