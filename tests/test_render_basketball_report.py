"""Tests for basketball report renderer."""

from __future__ import annotations

from tests.conftest import load_script_module


def _sample_scores() -> list[dict]:
    return [
        {
            "player": "LeBron James",
            "market": "points",
            "line": 25.5,
            "direction": "over",
            "score": 0.82,
            "confidence": "high",
            "explainability": {
                "risk_flags": [],
                "top_contributing_factors": [
                    {"factor": "recent_form_momentum", "score": 0.92, "weight": 0.25},
                    {"factor": "usage_rate_opportunity", "score": 0.80, "weight": 0.20},
                ],
            },
        },
        {
            "player": "Jayson Tatum",
            "market": "rebounds",
            "line": 8.5,
            "direction": "over",
            "score": 0.74,
            "confidence": "medium",
            "explainability": {
                "risk_flags": ["missing_data"],
                "top_contributing_factors": [
                    {"factor": "position_rebound_opportunity", "score": 0.85, "weight": 0.30},
                ],
            },
        },
        {
            "player": "Anthony Davis",
            "market": "assists",
            "line": 3.5,
            "direction": "under",
            "score": 0.65,
            "confidence": "medium",
            "explainability": {
                "risk_flags": ["low_volume"],
                "top_contributing_factors": [
                    {"factor": "pace_tempo", "score": 0.70, "weight": 0.15},
                ],
            },
        },
    ]


def _sample_match_inputs() -> dict:
    return {
        "home_team": "Lakers",
        "away_team": "Celtics",
        "match_date": "2026-06-01",
        "league": "nba",
        "game": {
            "home_pace": 100.2,
            "away_pace": 98.5,
            "projected_game_pace": 99.3,
            "spread": -3.5,
            "over_under_total": 224.5,
            "venue": "Crypto.com Arena",
            "home_win_prob": 0.55,
            "away_win_prob": 0.45,
            "home_rest_days": 2,
            "away_rest_days": 1,
        },
        "players": [
            {"player_name": "LeBron James", "team": "LAL", "minutes_proj": 35.0},
            {"player_name": "Jayson Tatum", "team": "BOS", "minutes_proj": 36.0},
            {"player_name": "Anthony Davis", "team": "LAL", "minutes_proj": 34.0},
        ],
        "lines": {
            "LeBron James": {"points": {"line": 25.5, "market_agreement": 0.95}},
        },
    }


class TestRenderBasketballReportHeader:
    def test_renders_header_with_teams_and_date(self) -> None:
        module = load_script_module("render_basketball_report.py")
        report = module.render_basketball_report(
            scores=_sample_scores(), match_inputs=_sample_match_inputs()
        )
        assert "Lakers" in report
        assert "Celtics" in report
        assert "2026-06-01" in report

    def test_renders_league(self) -> None:
        module = load_script_module("render_basketball_report.py")
        report = module.render_basketball_report(
            scores=_sample_scores(), match_inputs=_sample_match_inputs()
        )
        assert "NBA" in report or "nba" in report


class TestRenderBasketballReportGameContext:
    def test_renders_game_context_when_available(self) -> None:
        module = load_script_module("render_basketball_report.py")
        report = module.render_basketball_report(
            scores=_sample_scores(), match_inputs=_sample_match_inputs()
        )
        assert "99.3" in report or "100.2" in report
        assert "-3.5" in report
        assert "224.5" in report

    def test_renders_venue_when_available(self) -> None:
        module = load_script_module("render_basketball_report.py")
        report = module.render_basketball_report(
            scores=_sample_scores(), match_inputs=_sample_match_inputs()
        )
        assert "Crypto.com Arena" in report

    def test_handles_missing_game_context(self) -> None:
        module = load_script_module("render_basketball_report.py")
        inputs = _sample_match_inputs()
        inputs["game"] = {}
        report = module.render_basketball_report(
            scores=_sample_scores(), match_inputs=inputs
        )
        assert "Lakers" in report
        assert "Celtics" in report
        assert len(report) > 50


class TestRenderBasketballReportPicksTable:
    def test_renders_picks_table_with_all_fields(self) -> None:
        module = load_script_module("render_basketball_report.py")
        report = module.render_basketball_report(
            scores=_sample_scores(), match_inputs=_sample_match_inputs()
        )
        assert "LeBron James" in report
        assert "points" in report
        assert "over" in report.lower()
        assert "25.5" in report
        assert "high" in report.lower()

    def test_renders_multiple_picks_ranked(self) -> None:
        module = load_script_module("render_basketball_report.py")
        report = module.render_basketball_report(
            scores=_sample_scores(), match_inputs=_sample_match_inputs()
        )
        assert "Jayson Tatum" in report
        assert "Anthony Davis" in report
        lebron_pos = report.index("LeBron James")
        tatum_pos = report.index("Jayson Tatum")
        assert lebron_pos < tatum_pos


class TestRenderBasketballReportExplainability:
    def test_renders_explainability_section(self) -> None:
        module = load_script_module("render_basketball_report.py")
        report = module.render_basketball_report(
            scores=_sample_scores(), match_inputs=_sample_match_inputs()
        )
        assert "recent_form_momentum" in report
        assert "usage_rate_opportunity" in report

    def test_renders_risk_flags(self) -> None:
        module = load_script_module("render_basketball_report.py")
        report = module.render_basketball_report(
            scores=_sample_scores(), match_inputs=_sample_match_inputs()
        )
        assert "missing_data" in report


class TestRenderBasketballReportEdgeCases:
    def test_handles_empty_scores_gracefully(self) -> None:
        module = load_script_module("render_basketball_report.py")
        report = module.render_basketball_report(
            scores=[], match_inputs=_sample_match_inputs()
        )
        assert "Lakers" in report
        assert "no" in report.lower() or "No" in report

    def test_fallback_data_noted(self) -> None:
        module = load_script_module("render_basketball_report.py")
        inputs = _sample_match_inputs()
        inputs["game"] = {}
        inputs["players"] = [
            {"player_name": "Placeholder A", "team": "HOM", "minutes_proj": None},
        ]
        report = module.render_basketball_report(
            scores=_sample_scores(), match_inputs=inputs, used_fallback=True
        )
        assert "fallback" in report.lower() or "deterministic" in report.lower()
