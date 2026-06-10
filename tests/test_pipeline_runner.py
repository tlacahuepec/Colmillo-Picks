"""Tests for the shared multi-sport pipeline runner."""

from __future__ import annotations

from typing import Any

import pytest

from pick_request import PickRequest
from sport_module import SoccerModule
from pipeline_runner import PipelineRunner, PipelineResult, PipelineRunError


class FakeSportModule:
    """Minimal module for pipeline runner tests."""

    @property
    def sport_id(self) -> str:
        return "fake_sport"

    @property
    def supported_leagues(self) -> set[str]:
        return {"league_a"}

    @property
    def supported_markets(self) -> set[str]:
        return {"metric_x", "metric_y"}

    def collect_inputs(
        self, *, home_team: str, away_team: str, match_date: str, league: str | None = None
    ) -> dict[str, Any]:
        return {
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "players": [
                {"player_name": "Player A", "metric_x_line": 10.5, "metric_y_line": 5.5},
            ],
            "teams": [],
        }

    def score(
        self, match_inputs: dict[str, Any], *, markets: tuple[str, ...] = ()
    ) -> list[dict[str, Any]]:
        return [
            {"player": "Player A", "market": m, "score": 0.7, "line": 10.5,
             "direction": "over", "confidence": "high",
             "explainability": {"risk_flags": []}}
            for m in (markets or ("metric_x",))
        ]

    def explain(self, scored_pick: dict[str, Any]) -> str:
        return f"{scored_pick['player']} {scored_pick['market']} pick"


class TestPipelineRunnerWithFakeModule:
    def test_runner_executes_fake_module(self) -> None:
        module = FakeSportModule()
        request = PickRequest(
            sport="fake_sport",
            event_date="2026-06-01",
            home_team="Team A",
            away_team="Team B",
            markets=("metric_x",),
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)
        assert isinstance(result, PipelineResult)
        assert result.status == "success"
        assert len(result.scores) > 0

    def test_runner_returns_steps(self) -> None:
        module = FakeSportModule()
        request = PickRequest(
            sport="fake_sport",
            event_date="2026-06-01",
            home_team="Team A",
            away_team="Team B",
            markets=("metric_x",),
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)
        assert len(result.steps) >= 2
        step_names = [s["name"] for s in result.steps]
        assert "collect" in step_names
        assert "score" in step_names

    def test_runner_respects_top_n(self) -> None:
        module = FakeSportModule()
        request = PickRequest(
            sport="fake_sport",
            event_date="2026-06-01",
            home_team="Team A",
            away_team="Team B",
            markets=("metric_x", "metric_y"),
            top_n=1,
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)
        assert len(result.scores) <= 1


class TestPipelineRunnerWithSoccer:
    def test_soccer_request_runs_through_shared_runner(self) -> None:
        module = SoccerModule(allow_deterministic_fallback=True)
        request = PickRequest(
            sport="soccer",
            event_date="2026-06-01",
            home_team="Arsenal",
            away_team="Liverpool",
            markets=("passes", "shots"),
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)
        assert result.status == "success"
        assert len(result.scores) > 0
        assert result.scores[0]["player"] != ""


class TestPipelineRunnerErrors:
    def test_collect_failure_returns_error(self) -> None:
        class FailingModule(FakeSportModule):
            def collect_inputs(self, **kwargs: Any) -> dict[str, Any]:
                raise RuntimeError("Provider unavailable")

        module = FailingModule()
        request = PickRequest(
            sport="fake_sport",
            event_date="2026-06-01",
            home_team="A",
            away_team="B",
            markets=("metric_x",),
        )
        runner = PipelineRunner()
        with pytest.raises(PipelineRunError) as exc_info:
            runner.run(request=request, module=module)
        assert exc_info.value.stage == "collect"

    def test_score_failure_returns_error(self) -> None:
        class FailingScorerModule(FakeSportModule):
            def score(self, match_inputs: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
                raise ValueError("Scoring failed")

        module = FailingScorerModule()
        request = PickRequest(
            sport="fake_sport",
            event_date="2026-06-01",
            home_team="A",
            away_team="B",
            markets=("metric_x",),
        )
        runner = PipelineRunner()
        with pytest.raises(PipelineRunError) as exc_info:
            runner.run(request=request, module=module)
        assert exc_info.value.stage == "score"

    def test_collect_error_forwards_reason_to_error_details(self) -> None:
        class ReasonedError(RuntimeError):
            def __init__(self, msg: str, *, reason: str) -> None:
                self.reason = reason
                super().__init__(msg)

        class FailingWithReasonModule(FakeSportModule):
            def collect_inputs(self, **kwargs: Any) -> dict[str, Any]:
                raise ReasonedError("Missing data", reason="missing_prop_lines")

        module = FailingWithReasonModule()
        request = PickRequest(
            sport="fake_sport",
            event_date="2026-06-01",
            home_team="A",
            away_team="B",
            markets=("metric_x",),
        )
        runner = PipelineRunner()
        with pytest.raises(PipelineRunError) as exc_info:
            runner.run(request=request, module=module)
        assert exc_info.value.stage == "collect"
        assert exc_info.value.error_details is not None
        assert exc_info.value.error_details["reason"] == "missing_prop_lines"
        assert exc_info.value.error_details["sport"] == "fake_sport"

    def test_score_error_forwards_reason_to_error_details(self) -> None:
        class ReasonedError(RuntimeError):
            def __init__(self, msg: str, *, reason: str) -> None:
                self.reason = reason
                super().__init__(msg)

        class FailingScorerWithReasonModule(FakeSportModule):
            def score(self, match_inputs: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
                raise ReasonedError("Hitter data missing", reason="hitter_inputs_unavailable")

        module = FailingScorerWithReasonModule()
        request = PickRequest(
            sport="fake_sport",
            event_date="2026-06-01",
            home_team="A",
            away_team="B",
            markets=("metric_x",),
        )
        runner = PipelineRunner()
        with pytest.raises(PipelineRunError) as exc_info:
            runner.run(request=request, module=module)
        assert exc_info.value.stage == "score"
        assert exc_info.value.error_details is not None
        assert exc_info.value.error_details["reason"] == "hitter_inputs_unavailable"


class TestPickDiversityConstraints:
    """Picks should be capped at 3 per player and ensure both teams represented."""

    def _make_scores(self, players_and_teams: list[tuple[str, str]], *, base_score: float = 0.9) -> list[dict[str, Any]]:
        scores = []
        for i, (player, team) in enumerate(players_and_teams):
            scores.append({
                "player": player,
                "team": team,
                "market": f"market_{i}",
                "score": base_score - i * 0.01,
                "line": 10.5,
                "direction": "over",
                "confidence": "high",
                "explainability": {"risk_flags": []},
            })
        return scores

    def test_max_3_picks_per_player(self) -> None:
        """No player should appear more than 3 times in the final picks."""

        class DominantPlayerModule(FakeSportModule):
            @property
            def sport_id(self) -> str:
                return "basketball"

            def collect_inputs(self, **kwargs: Any) -> dict[str, Any]:
                return {"home_team": "NYK", "away_team": "SAS", "match_date": "2026-06-08", "players": [], "lines": {}, "game": {}}

            def score(self, match_inputs: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
                scores = []
                for i in range(6):
                    scores.append({"player": "Wembanyama", "team": "SAS", "market": f"m{i}", "score": 0.95 - i * 0.01, "line": 10.5, "direction": "over", "confidence": "high", "explainability": {"risk_flags": []}})
                for i in range(4):
                    scores.append({"player": "Brunson", "team": "NYK", "market": f"m{i}", "score": 0.80 - i * 0.01, "line": 8.5, "direction": "over", "confidence": "medium", "explainability": {"risk_flags": []}})
                return scores

        module = DominantPlayerModule()
        request = PickRequest(
            sport="basketball",
            event_date="2026-06-08",
            home_team="NYK",
            away_team="SAS",
            markets=("points", "rebounds", "assists"),
            top_n=10,
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)

        from collections import Counter
        player_counts = Counter(s["player"] for s in result.scores)
        for player, count in player_counts.items():
            assert count <= 3, f"{player} has {count} picks, max is 3"

    def test_both_teams_represented_min_3(self) -> None:
        """At least 3 of the top picks should come from each team."""

        class HomeHeavyModule(FakeSportModule):
            @property
            def sport_id(self) -> str:
                return "basketball"

            def collect_inputs(self, **kwargs: Any) -> dict[str, Any]:
                return {"home_team": "NYK", "away_team": "SAS", "match_date": "2026-06-08", "players": [], "lines": {}, "game": {}}

            def score(self, match_inputs: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
                scores = []
                home_players = ["Brunson", "Hart", "Bridges", "Towns"]
                away_players = ["Wembanyama", "Vassell", "Johnson", "Barnes"]
                for i, p in enumerate(home_players):
                    for j in range(3):
                        scores.append({"player": p, "team": "NYK", "market": f"m{j}", "score": 0.95 - i * 0.05 - j * 0.01, "line": 10.5, "direction": "over", "confidence": "high", "explainability": {"risk_flags": []}})
                for i, p in enumerate(away_players):
                    for j in range(3):
                        scores.append({"player": p, "team": "SAS", "market": f"m{j}", "score": 0.60 - i * 0.05 - j * 0.01, "line": 8.5, "direction": "over", "confidence": "medium", "explainability": {"risk_flags": []}})
                return scores

        module = HomeHeavyModule()
        request = PickRequest(
            sport="basketball",
            event_date="2026-06-08",
            home_team="NYK",
            away_team="SAS",
            markets=("points", "rebounds", "assists"),
            top_n=10,
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)

        home_picks = [s for s in result.scores if s.get("team") == "NYK"]
        away_picks = [s for s in result.scores if s.get("team") == "SAS"]
        assert len(home_picks) >= 3, f"Home team only has {len(home_picks)} picks, need at least 3"
        assert len(away_picks) >= 3, f"Away team only has {len(away_picks)} picks, need at least 3"

    def test_diversity_does_not_apply_to_soccer(self) -> None:
        """Soccer picks should not be constrained by basketball diversity rules."""

        class SoccerDominantModule(FakeSportModule):
            @property
            def sport_id(self) -> str:
                return "soccer"

            def collect_inputs(self, **kwargs: Any) -> dict[str, Any]:
                return {"home_team": "Arsenal", "away_team": "Liverpool", "match_date": "2026-06-01", "players": [], "lines": {}, "game": {}}

            def score(self, match_inputs: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
                scores = []
                for i in range(5):
                    scores.append({"player": "Saka", "team": "ARS", "market": f"m{i}", "score": 0.95 - i * 0.01, "line": 2.5, "direction": "over", "confidence": "high", "explainability": {"risk_flags": []}})
                return scores

        module = SoccerDominantModule()
        request = PickRequest(
            sport="soccer",
            event_date="2026-06-01",
            home_team="Arsenal",
            away_team="Liverpool",
            markets=("passes", "shots"),
            top_n=5,
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)

        from collections import Counter
        player_counts = Counter(s["player"] for s in result.scores)
        assert player_counts["Saka"] == 5
