"""Tests for baseball sport module skeleton."""

from __future__ import annotations

from baseball_module import BaseballModule
from pick_request import PickRequest
from pipeline_runner import PipelineRunner, PipelineResult
from sport_module import SportModule, SportModuleRegistry


class TestBaseballModuleProtocol:
    def test_baseball_module_satisfies_sport_module_protocol(self) -> None:
        module = BaseballModule()
        assert isinstance(module, SportModule)

    def test_sport_id_is_baseball(self) -> None:
        module = BaseballModule()
        assert module.sport_id == "baseball"

    def test_supported_markets(self) -> None:
        module = BaseballModule()
        expected = {"hits", "total_bases", "runs", "rbi", "home_runs", "strikeouts", "walks", "pitcher_outs"}
        assert module.supported_markets == expected

    def test_supported_leagues(self) -> None:
        module = BaseballModule()
        assert module.supported_leagues == {"mlb"}

    def test_npb_kbo_not_in_supported_leagues(self) -> None:
        module = BaseballModule()
        assert "npb" not in module.supported_leagues
        assert "kbo" not in module.supported_leagues


class TestBaseballModuleRegistry:
    def test_baseball_registers_in_sport_module_registry(self) -> None:
        registry = SportModuleRegistry()
        module = BaseballModule()
        registry.register(module)
        assert registry.get("baseball") is module

    def test_baseball_in_default_registry(self) -> None:
        from sport_module import get_sport_module

        module = get_sport_module("baseball")
        assert module.sport_id == "baseball"

    def test_baseball_does_not_conflict_with_other_sports(self) -> None:
        from basketball_module import BasketballModule
        from sport_module import SoccerModule

        registry = SportModuleRegistry()
        registry.register(SoccerModule())
        registry.register(BasketballModule())
        registry.register(BaseballModule())
        assert registry.get("soccer").sport_id == "soccer"
        assert registry.get("basketball").sport_id == "basketball"
        assert registry.get("baseball").sport_id == "baseball"


class TestBaseballPlaceholderScoring:
    def test_collect_inputs_returns_structured_data(self) -> None:
        module = BaseballModule()
        inputs = module.collect_inputs(
            home_team="Yankees",
            away_team="Red Sox",
            match_date="2026-06-01",
            league="mlb",
        )
        assert "home_team" in inputs
        assert "away_team" in inputs
        assert "players" in inputs
        assert len(inputs["players"]) > 0

    def test_score_returns_valid_picks(self) -> None:
        module = BaseballModule()
        inputs = module.collect_inputs(
            home_team="Yankees",
            away_team="Red Sox",
            match_date="2026-06-01",
        )
        scores = module.score(inputs, markets=("hits", "total_bases"))
        assert len(scores) > 0
        for pick in scores:
            assert "player" in pick
            assert "market" in pick
            assert "score" in pick
            assert "line" in pick
            assert "direction" in pick
            assert "confidence" in pick
            assert pick["market"] in ("hits", "total_bases")

    def test_score_all_markets_when_none_specified(self) -> None:
        module = BaseballModule()
        inputs = module.collect_inputs(
            home_team="Yankees",
            away_team="Red Sox",
            match_date="2026-06-01",
        )
        scores = module.score(inputs)
        markets_seen = {s["market"] for s in scores}
        assert len(markets_seen) >= 2

    def test_explain_returns_nonempty_string(self) -> None:
        module = BaseballModule()
        pick = {
            "player": "Aaron Judge",
            "market": "home_runs",
            "direction": "over",
            "line": 0.5,
            "confidence": "medium",
            "score": 0.6,
        }
        explanation = module.explain(pick)
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "Aaron Judge" in explanation


class TestBaseballPipelineIntegration:
    def test_baseball_request_runs_through_pipeline(self) -> None:
        module = BaseballModule()
        request = PickRequest(
            sport="baseball",
            event_date="2026-06-01",
            home_team="Yankees",
            away_team="Red Sox",
            markets=("hits", "strikeouts"),
            league="mlb",
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)
        assert isinstance(result, PipelineResult)
        assert result.status == "success"
        assert len(result.scores) > 0
