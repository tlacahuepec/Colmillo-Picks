"""RED tests for slate orchestration logic."""

from __future__ import annotations

from typing import Any

import pytest

from services.api.slate_orchestration import (
    SlateOrchestrationDeps,
    execute_slate_job,
)


def _discovery_response(sports: list[str], matches_per_sport: int = 2) -> dict[str, Any]:
    results: dict[str, Any] = {}
    teams = {
        "soccer": [("Arsenal", "Liverpool"), ("Barcelona", "Real Madrid")],
        "basketball": [("Lakers", "Celtics"), ("Warriors", "Bucks")],
        "baseball": [("Yankees", "Red Sox"), ("Dodgers", "Cubs")],
    }
    for sport in sports:
        sport_teams = teams.get(sport, [("TeamA", "TeamB")])
        matches = []
        for i, (home, away) in enumerate(sport_teams[:matches_per_sport]):
            matches.append({
                "sport": sport,
                "home_team": home,
                "away_team": away,
                "event_date": "2026-06-01",
                "league": "test_league",
                "competition": "Test",
                "kickoff_utc": f"2026-06-01T{18 + i}:00:00Z",
                "importance": "high",
                "notes": None,
                "source_provider": "fake",
                "source_model": "test-model",
                "sources": [],
                "data_quality": {"confidence": "medium", "missing_fields": []},
            })
        results[sport] = {"matches": matches, "error": None, "data_quality": {"status": "ok"}}
    return {
        "date_utc": "2026-06-01",
        "generated_at_utc": "2026-06-01T12:00:00Z",
        "limit_per_sport": matches_per_sport,
        "results": results,
    }


def _pipeline_result(sport: str, player: str, score: float) -> list[dict[str, Any]]:
    return [
        {
            "player": player,
            "market": "points" if sport == "basketball" else "passes",
            "line": 20.5,
            "direction": "over",
            "score": score,
            "confidence": "high",
            "explainability": {"risk_flags": []},
        }
    ]


def _make_deps(
    *,
    discovery_response: dict[str, Any] | None = None,
    pipeline_results: dict[str, list[dict]] | None = None,
    pipeline_error_teams: set[str] | None = None,
    discovery_raises: Exception | None = None,
) -> SlateOrchestrationDeps:
    def discover(*, date_utc, sports, limit_per_sport, timezone=None):
        if discovery_raises:
            raise discovery_raises
        return discovery_response or _discovery_response(sports)

    def run_pipeline(*, sport, home_team, away_team, event_date, markets):
        if pipeline_error_teams and home_team in pipeline_error_teams:
            raise RuntimeError(f"Pipeline failed for {home_team}")
        key = f"{sport}:{home_team}"
        if pipeline_results and key in pipeline_results:
            return pipeline_results[key]
        return _pipeline_result(sport, f"{home_team} Star", 0.75)

    return SlateOrchestrationDeps(
        discover_matches=discover,
        run_match_pipeline=run_pipeline,
    )


class TestOrchestratorCallsDiscoveryThenPipelines:
    def test_calls_in_correct_order(self) -> None:
        call_log: list[str] = []

        def discover(*, date_utc, sports, limit_per_sport, timezone=None):
            call_log.append("discovery")
            return _discovery_response(["soccer"], matches_per_sport=1)

        def run_pipeline(*, sport, home_team, away_team, event_date, markets):
            call_log.append(f"pipeline:{home_team}")
            return _pipeline_result(sport, f"{home_team} Player", 0.8)

        deps = SlateOrchestrationDeps(
            discover_matches=discover,
            run_match_pipeline=run_pipeline,
        )
        request = {"date": "2026-06-01", "sports": ["soccer"], "max_matches_per_sport": 1, "top_n": 5}
        execute_slate_job(request_dict=request, deps=deps)

        assert call_log[0] == "discovery"
        assert any("pipeline:" in c for c in call_log[1:])


class TestCandidatesNormalizedAndRankedAcrossSports:
    def test_mixed_sports_ranked_by_score(self) -> None:
        pipeline_results = {
            "soccer:Arsenal": _pipeline_result("soccer", "Saka", 0.9),
            "basketball:Lakers": _pipeline_result("basketball", "LeBron", 0.7),
        }
        deps = _make_deps(
            discovery_response=_discovery_response(["soccer", "basketball"], matches_per_sport=1),
            pipeline_results=pipeline_results,
        )
        request = {
            "date": "2026-06-01",
            "sports": ["soccer", "basketball"],
            "max_matches_per_sport": 1,
            "top_n": 10,
        }
        result = execute_slate_job(request_dict=request, deps=deps)

        assert len(result.candidates) == 2
        assert result.candidates[0].player == "Saka"
        assert result.candidates[0].normalized_score > result.candidates[1].normalized_score


class TestPartialPipelineFailure:
    def test_still_yields_candidates(self) -> None:
        deps = _make_deps(
            discovery_response=_discovery_response(["soccer"], matches_per_sport=2),
            pipeline_error_teams={"Barcelona"},
        )
        request = {
            "date": "2026-06-01",
            "sports": ["soccer"],
            "max_matches_per_sport": 2,
            "top_n": 10,
        }
        result = execute_slate_job(request_dict=request, deps=deps)

        assert len(result.candidates) >= 1
        assert result.matches_succeeded < result.matches_attempted

    def test_match_runs_include_failure_metadata(self) -> None:
        deps = _make_deps(
            discovery_response=_discovery_response(["soccer"], matches_per_sport=2),
            pipeline_error_teams={"Barcelona"},
        )
        request = {
            "date": "2026-06-01",
            "sports": ["soccer"],
            "max_matches_per_sport": 2,
            "top_n": 10,
        }
        result = execute_slate_job(request_dict=request, deps=deps)

        failed_runs = [r for r in result.match_runs if r["status"] == "failed"]
        assert len(failed_runs) == 1
        assert failed_runs[0]["error_message"] is not None


class TestAllPipelineFailures:
    def test_returns_empty_candidates(self) -> None:
        deps = _make_deps(
            discovery_response=_discovery_response(["soccer"], matches_per_sport=2),
            pipeline_error_teams={"Arsenal", "Barcelona"},
        )
        request = {
            "date": "2026-06-01",
            "sports": ["soccer"],
            "max_matches_per_sport": 2,
            "top_n": 10,
        }
        result = execute_slate_job(request_dict=request, deps=deps)

        assert result.candidates == []
        assert result.matches_succeeded == 0
        assert result.matches_attempted == 2


class TestTimingCaptured:
    def test_discovery_and_total_latency(self) -> None:
        deps = _make_deps(
            discovery_response=_discovery_response(["soccer"], matches_per_sport=1),
        )
        request = {
            "date": "2026-06-01",
            "sports": ["soccer"],
            "max_matches_per_sport": 1,
            "top_n": 5,
        }
        result = execute_slate_job(request_dict=request, deps=deps)

        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert result.discovery_latency_ms is not None
        assert result.discovery_latency_ms >= 0


class TestDiscoveryFailure:
    def test_raises_when_discovery_fails(self) -> None:
        deps = _make_deps(discovery_raises=RuntimeError("LLM timeout"))
        request = {
            "date": "2026-06-01",
            "sports": ["soccer"],
            "max_matches_per_sport": 3,
            "top_n": 10,
        }

        with pytest.raises(RuntimeError, match="LLM timeout"):
            execute_slate_job(request_dict=request, deps=deps)


class TestTimezonePassthrough:
    def test_timezone_passed_to_discovery(self) -> None:
        captured: dict[str, Any] = {}

        def discover(*, date_utc, sports, limit_per_sport, timezone=None):
            captured["timezone"] = timezone
            return _discovery_response(sports, matches_per_sport=1)

        def run_pipeline(*, sport, home_team, away_team, event_date, markets):
            return _pipeline_result(sport, f"{home_team} Star", 0.75)

        deps = SlateOrchestrationDeps(
            discover_matches=discover,
            run_match_pipeline=run_pipeline,
        )
        request = {
            "date": "2026-06-01",
            "sports": ["soccer"],
            "max_matches_per_sport": 1,
            "top_n": 5,
            "timezone": "America/Chicago",
        }
        execute_slate_job(request_dict=request, deps=deps)

        assert captured["timezone"] == "America/Chicago"

    def test_timezone_defaults_to_none_when_absent(self) -> None:
        captured: dict[str, Any] = {}

        def discover(*, date_utc, sports, limit_per_sport, timezone=None):
            captured["timezone"] = timezone
            return _discovery_response(sports, matches_per_sport=1)

        def run_pipeline(*, sport, home_team, away_team, event_date, markets):
            return _pipeline_result(sport, f"{home_team} Star", 0.75)

        deps = SlateOrchestrationDeps(
            discover_matches=discover,
            run_match_pipeline=run_pipeline,
        )
        request = {
            "date": "2026-06-01",
            "sports": ["soccer"],
            "max_matches_per_sport": 1,
            "top_n": 5,
        }
        execute_slate_job(request_dict=request, deps=deps)

        assert captured["timezone"] is None
