"""Tests for MLB settlement grading logic."""

from __future__ import annotations

from mlb_settlement import (
    grade_prop,
    grade_moneyline,
    grade_run_line,
    grade_game_outcomes,
    SettlementResult,
)


class TestOverUnderProps:
    def test_over_win(self):
        result = grade_prop(actual=2, line=1.5, direction="over")
        assert result == SettlementResult.WIN

    def test_over_loss(self):
        result = grade_prop(actual=1, line=1.5, direction="over")
        assert result == SettlementResult.LOSS

    def test_under_win(self):
        result = grade_prop(actual=1, line=1.5, direction="under")
        assert result == SettlementResult.WIN

    def test_under_loss(self):
        result = grade_prop(actual=2, line=1.5, direction="under")
        assert result == SettlementResult.LOSS

    def test_push_on_whole_line(self):
        result = grade_prop(actual=2, line=2.0, direction="over")
        assert result == SettlementResult.PUSH

    def test_push_on_whole_line_under(self):
        result = grade_prop(actual=2, line=2.0, direction="under")
        assert result == SettlementResult.PUSH

    def test_half_line_no_push_over(self):
        result = grade_prop(actual=2, line=1.5, direction="over")
        assert result == SettlementResult.WIN

    def test_half_line_no_push_under(self):
        result = grade_prop(actual=1, line=1.5, direction="under")
        assert result == SettlementResult.WIN

    def test_zero_actual_under_win(self):
        result = grade_prop(actual=0, line=0.5, direction="under")
        assert result == SettlementResult.WIN

    def test_zero_actual_over_loss(self):
        result = grade_prop(actual=0, line=0.5, direction="over")
        assert result == SettlementResult.LOSS


class TestMoneyline:
    def test_team_wins(self):
        result = grade_moneyline(team_won=True)
        assert result == SettlementResult.WIN

    def test_team_loses(self):
        result = grade_moneyline(team_won=False)
        assert result == SettlementResult.LOSS


class TestRunLine:
    def test_run_line_cover(self):
        result = grade_run_line(margin=3, spread=-1.5)
        assert result == SettlementResult.WIN

    def test_run_line_fail(self):
        result = grade_run_line(margin=1, spread=-1.5)
        assert result == SettlementResult.LOSS

    def test_run_line_push_exact(self):
        result = grade_run_line(margin=2, spread=-2.0)
        assert result == SettlementResult.PUSH

    def test_underdog_run_line_win(self):
        result = grade_run_line(margin=-1, spread=1.5)
        assert result == SettlementResult.WIN

    def test_underdog_run_line_loss(self):
        result = grade_run_line(margin=-3, spread=1.5)
        assert result == SettlementResult.LOSS


class TestVoidConditions:
    def test_rain_shortened_game_void(self):
        results = grade_game_outcomes(
            picks=[{"player": "Judge", "market": "hits", "direction": "over", "line": 1.5}],
            actuals={"Judge": {"hits": 2}},
            game_status="rain_shortened",
            innings_played=4,
        )
        assert results[0]["result"] == SettlementResult.VOID

    def test_suspended_game_void(self):
        results = grade_game_outcomes(
            picks=[{"player": "Judge", "market": "hits", "direction": "over", "line": 1.5}],
            actuals={"Judge": {"hits": 2}},
            game_status="suspended",
        )
        assert results[0]["result"] == SettlementResult.VOID

    def test_rain_shortened_5_innings_valid(self):
        results = grade_game_outcomes(
            picks=[{"player": "Judge", "market": "hits", "direction": "over", "line": 1.5}],
            actuals={"Judge": {"hits": 2}},
            game_status="rain_shortened",
            innings_played=5,
        )
        assert results[0]["result"] == SettlementResult.WIN

    def test_pitcher_prop_voided_if_pulled_early(self):
        results = grade_game_outcomes(
            picks=[{"player": "Cole", "market": "pitcher_outs", "direction": "over", "line": 17.5}],
            actuals={"Cole": {"pitcher_outs": 6}},
            game_status="final",
            pitcher_voided={"Cole"},
        )
        assert results[0]["result"] == SettlementResult.VOID


class TestGradeGameOutcomes:
    def test_multiple_picks_graded(self):
        results = grade_game_outcomes(
            picks=[
                {"player": "Judge", "market": "hits", "direction": "over", "line": 1.5},
                {"player": "Soto", "market": "total_bases", "direction": "under", "line": 2.5},
            ],
            actuals={
                "Judge": {"hits": 2},
                "Soto": {"total_bases": 1},
            },
            game_status="final",
        )
        assert len(results) == 2
        assert results[0]["result"] == SettlementResult.WIN
        assert results[1]["result"] == SettlementResult.WIN

    def test_missing_actual_voids_pick(self):
        results = grade_game_outcomes(
            picks=[{"player": "Unknown", "market": "hits", "direction": "over", "line": 1.5}],
            actuals={},
            game_status="final",
        )
        assert results[0]["result"] == SettlementResult.VOID

    def test_complete_game_grades_normally(self):
        results = grade_game_outcomes(
            picks=[
                {"player": "Judge", "market": "home_runs", "direction": "over", "line": 0.5},
            ],
            actuals={"Judge": {"home_runs": 1}},
            game_status="final",
        )
        assert results[0]["result"] == SettlementResult.WIN
