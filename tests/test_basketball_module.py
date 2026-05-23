"""Tests for basketball sport module skeleton."""

from __future__ import annotations

from basketball_module import BasketballModule
from pick_request import PickRequest
from pipeline_runner import PipelineRunner, PipelineResult
from sport_module import SportModule, SportModuleRegistry


class TestBasketballModuleProtocol:
    def test_basketball_module_satisfies_sport_module_protocol(self) -> None:
        module = BasketballModule()
        assert isinstance(module, SportModule)

    def test_sport_id_is_basketball(self) -> None:
        module = BasketballModule()
        assert module.sport_id == "basketball"

    def test_supported_markets(self) -> None:
        module = BasketballModule()
        expected = {"points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers", "fantasy_score"}
        assert module.supported_markets == expected

    def test_supported_leagues(self) -> None:
        module = BasketballModule()
        assert "nba" in module.supported_leagues


class TestBasketballModuleRegistry:
    def test_basketball_registers_in_sport_module_registry(self) -> None:
        registry = SportModuleRegistry()
        module = BasketballModule()
        registry.register(module)
        assert registry.get("basketball") is module

    def test_basketball_does_not_conflict_with_soccer(self) -> None:
        from sport_module import SoccerModule

        registry = SportModuleRegistry()
        registry.register(SoccerModule())
        registry.register(BasketballModule())
        assert registry.get("soccer").sport_id == "soccer"
        assert registry.get("basketball").sport_id == "basketball"


class TestBasketballPlaceholderScoring:
    def test_collect_inputs_returns_structured_data(self) -> None:
        module = BasketballModule()
        inputs = module.collect_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
            league="nba",
        )
        assert "home_team" in inputs
        assert "away_team" in inputs
        assert "players" in inputs
        assert len(inputs["players"]) > 0

    def test_score_returns_valid_picks(self) -> None:
        module = BasketballModule()
        inputs = module.collect_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
        )
        scores = module.score(inputs, markets=("points", "assists"))
        assert len(scores) > 0
        for pick in scores:
            assert "player" in pick
            assert "market" in pick
            assert "score" in pick
            assert "line" in pick
            assert "direction" in pick
            assert "confidence" in pick
            assert pick["market"] in ("points", "assists")

    def test_score_all_markets_when_none_specified(self) -> None:
        module = BasketballModule()
        inputs = module.collect_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
        )
        scores = module.score(inputs)
        markets_seen = {s["market"] for s in scores}
        assert len(markets_seen) >= 2

    def test_explain_returns_nonempty_string(self) -> None:
        module = BasketballModule()
        pick = {
            "player": "LeBron James",
            "market": "points",
            "direction": "over",
            "line": 25.5,
            "confidence": "high",
            "score": 0.8,
        }
        explanation = module.explain(pick)
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "LeBron James" in explanation


class TestBasketballPipelineIntegration:
    def test_basketball_request_runs_through_pipeline(self) -> None:
        module = BasketballModule()
        request = PickRequest(
            sport="basketball",
            event_date="2026-06-01",
            home_team="Lakers",
            away_team="Celtics",
            markets=("points", "rebounds"),
            league="nba",
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)
        assert isinstance(result, PipelineResult)
        assert result.status == "success"
        assert len(result.scores) > 0

    def test_basketball_pipeline_does_not_affect_soccer(self) -> None:
        from sport_module import SoccerModule

        soccer_module = SoccerModule(allow_deterministic_fallback=True)
        request = PickRequest(
            sport="soccer",
            event_date="2026-06-01",
            home_team="Arsenal",
            away_team="Liverpool",
            markets=("passes",),
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=soccer_module)
        assert result.status == "success"
        assert len(result.scores) > 0
