"""Tests for MLB end-to-end pipeline wiring (Story 11)."""

from __future__ import annotations

from typing import Any

from baseball_module import BaseballModule


def _enriched_player(**overrides: Any) -> dict[str, Any]:
    base = {
        "player_name": "Aaron Judge",
        "player_type": "batter",
        "team": "NYY",
        "batting_order": 2,
        "handedness": "R",
        "opposing_pitcher_hand": "L",
        "hits_per_game": 1.4,
        "hits_last5_per_game": 1.8,
        "tb_per_game": 2.5,
        "tb_last5_per_game": 3.2,
        "hr_per_game": 0.35,
        "hr_last5_per_game": 0.6,
        "runs_per_game": 0.9,
        "runs_last5_per_game": 1.2,
        "rbi_per_game": 1.2,
        "rbi_last5_per_game": 1.6,
        "bb_per_game": 0.8,
        "bb_last5_per_game": 0.6,
        "k_per_game": 1.8,
        "k_last5_per_game": 1.4,
        "park_factor": 0.55,
        "hr_factor": 0.6,
        "temp_f": 78,
        "wind_direction": "out to center",
        "team_implied_total": 5.2,
        "home_away": "home",
        "opp_k_rate": 0.22,
        "market_agreement": 0.7,
    }
    base.update(overrides)
    return base


class TestBaseballModuleScoring:
    def test_score_uses_real_engine(self):
        module = BaseballModule()
        match_inputs = {
            "home_team": "NYY",
            "away_team": "BOS",
            "match_date": "2026-05-25",
            "league": "mlb",
            "players": [_enriched_player()],
            "lines": {"Aaron Judge": {"hits": 1.5, "home_runs": 0.5}},
        }
        scores = module.score(match_inputs, markets=("hits", "home_runs"))
        assert len(scores) > 0
        for s in scores:
            assert s["score"] != 0.55, "Should not return placeholder score"
            assert "placeholder_scoring" not in s.get("explainability", {}).get("risk_flags", [])

    def test_score_returns_proper_structure(self):
        module = BaseballModule()
        match_inputs = {
            "home_team": "NYY",
            "away_team": "BOS",
            "match_date": "2026-05-25",
            "league": "mlb",
            "players": [_enriched_player()],
            "lines": {"Aaron Judge": {"hits": 1.5}},
        }
        scores = module.score(match_inputs, markets=("hits",))
        assert len(scores) == 1
        pick = scores[0]
        assert pick["player"] == "Aaron Judge"
        assert pick["market"] == "hits"
        assert "direction" in pick
        assert "confidence" in pick
        assert pick["confidence"] in ("high", "medium", "low")
        assert "explainability" in pick
        assert "top_contributing_factors" in pick["explainability"]

    def test_score_empty_players_returns_empty(self):
        module = BaseballModule()
        match_inputs = {
            "home_team": "NYY",
            "away_team": "BOS",
            "match_date": "2026-05-25",
            "players": [],
            "lines": {},
        }
        scores = module.score(match_inputs, markets=("hits",))
        assert scores == []

    def test_explain_uses_real_explainer(self):
        module = BaseballModule()
        pick = {
            "player": "Aaron Judge",
            "market": "home_runs",
            "direction": "over",
            "line": 0.5,
            "score": 0.82,
            "confidence": "high",
            "explainability": {
                "risk_flags": [],
                "top_contributing_factors": [
                    {"factor": "ballpark_factor", "score": 0.9, "weight": 0.2},
                ],
            },
        }
        explanation = module.explain(pick)
        assert "Aaron Judge" in explanation
        assert "home_runs" in explanation
        assert "not a prediction" in explanation.lower()


class TestBaseballModulePipelineIntegration:
    def test_collect_score_explain_pipeline(self):
        module = BaseballModule()
        inputs = module.collect_inputs(
            home_team="NYY", away_team="BOS", match_date="2026-05-25"
        )
        assert inputs["home_team"] == "NYY"
        assert inputs["league"] == "mlb"

        scores = module.score(inputs)
        assert len(scores) > 0

        for pick in scores:
            explanation = module.explain(pick)
            assert isinstance(explanation, str)
            assert len(explanation) > 0

    def test_pipeline_runner_integration(self):
        from pick_request import PickRequest
        from pipeline_runner import PipelineRunner

        module = BaseballModule()
        req = PickRequest(
            sport="baseball",
            event_date="2026-05-25",
            home_team="NYY",
            away_team="BOS",
            markets=("hits", "home_runs"),
            top_n=5,
            league="mlb",
        )
        runner = PipelineRunner()
        result = runner.run(request=req, module=module)
        assert result.scores
        assert result.match_inputs["home_team"] == "NYY"
        assert len(result.steps) >= 2

    def test_report_renders_for_baseball_scores(self):
        from render_baseball_report import render_baseball_report

        module = BaseballModule()
        inputs = module.collect_inputs(
            home_team="NYY", away_team="BOS", match_date="2026-05-25"
        )
        scores = module.score(inputs, markets=("hits",))

        report = render_baseball_report(match_context=inputs, picks=scores)
        assert "NYY" in report
        assert "BOS" in report
        assert "1-800-522-4700" in report

    def test_trace_builds_for_baseball(self):
        from baseball_trace import MLBTraceRecord, PickTrace, compute_input_hash

        module = BaseballModule()
        inputs = module.collect_inputs(
            home_team="NYY", away_team="BOS", match_date="2026-05-25"
        )
        scores = module.score(inputs, markets=("hits",))

        picks = [
            PickTrace(
                player=s["player"],
                market=s["market"],
                direction=s["direction"],
                line=s["line"],
                score=s["score"],
                confidence=s["confidence"],
            )
            for s in scores
        ]
        record = MLBTraceRecord(
            run_id="test-run",
            input_hash=compute_input_hash(inputs),
            picks=picks,
        )
        assert record.sport == "baseball"
        assert record.no_guarantee_flag is True
        assert len(record.picks) > 0


class TestSoccerBasketballRegression:
    def test_soccer_module_still_works(self):
        from sport_module import get_sport_module

        module = get_sport_module("soccer")
        assert module.sport_id == "soccer"
        assert "shots" in module.supported_markets

    def test_basketball_module_still_works(self):
        from sport_module import get_sport_module

        module = get_sport_module("basketball")
        assert module.sport_id == "basketball"
        assert "points" in module.supported_markets

    def test_baseball_module_registered(self):
        from sport_module import get_sport_module

        module = get_sport_module("baseball")
        assert module.sport_id == "baseball"
        assert "hits" in module.supported_markets
