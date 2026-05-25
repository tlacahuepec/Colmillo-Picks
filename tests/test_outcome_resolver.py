"""Tests for the outcome resolution engine."""

from __future__ import annotations

from unittest.mock import MagicMock

from outcome_resolver import (
    OutcomeResolver,
    PostMatchPlayerStat,
    ResolutionResult,
)


class TestResolutionResult:
    def test_win_on_over_actual_above_line(self):
        result = ResolutionResult.from_comparison(
            actual=2, line=1.5, direction="over"
        )
        assert result == "win"

    def test_loss_on_over_actual_below_line(self):
        result = ResolutionResult.from_comparison(
            actual=1, line=1.5, direction="over"
        )
        assert result == "loss"

    def test_push_on_exact_line(self):
        result = ResolutionResult.from_comparison(
            actual=2, line=2.0, direction="over"
        )
        assert result == "push"

    def test_win_on_under_actual_below_line(self):
        result = ResolutionResult.from_comparison(
            actual=1, line=1.5, direction="under"
        )
        assert result == "win"

    def test_void_for_dnp(self):
        result = ResolutionResult.void()
        assert result == "void"


class TestOutcomeResolver:
    def test_resolves_single_pick_high_confidence(self):
        stats_provider = MagicMock()
        stats_provider.fetch_player_stats.return_value = [
            PostMatchPlayerStat(
                player="Aaron Judge",
                market="hits",
                actual_value=2,
                confidence="high",
            )
        ]
        recorder = MagicMock()

        resolver = OutcomeResolver(
            stats_provider=stats_provider, outcome_recorder=recorder
        )
        picks = [
            {
                "rank": 1,
                "player": "Aaron Judge",
                "market": "hits",
                "line": 1.5,
                "direction": "over",
            }
        ]

        results = resolver.resolve(pick_id="pick-1", picks=picks)

        assert len(results) == 1
        assert results[0]["result"] == "win"
        recorder.assert_called_once()

    def test_skips_low_confidence(self):
        stats_provider = MagicMock()
        stats_provider.fetch_player_stats.return_value = [
            PostMatchPlayerStat(
                player="Judge",
                market="hits",
                actual_value=2,
                confidence="low",
            )
        ]
        recorder = MagicMock()

        resolver = OutcomeResolver(
            stats_provider=stats_provider, outcome_recorder=recorder
        )
        picks = [{"rank": 1, "player": "Judge", "market": "hits", "line": 1.5, "direction": "over"}]

        results = resolver.resolve(pick_id="pick-1", picks=picks)

        assert len(results) == 0
        recorder.assert_not_called()

    def test_voids_when_player_not_found(self):
        stats_provider = MagicMock()
        stats_provider.fetch_player_stats.return_value = []
        recorder = MagicMock()

        resolver = OutcomeResolver(
            stats_provider=stats_provider, outcome_recorder=recorder
        )
        picks = [{"rank": 1, "player": "Unknown", "market": "hits", "line": 1.5, "direction": "over"}]

        results = resolver.resolve(pick_id="pick-1", picks=picks)

        assert len(results) == 1
        assert results[0]["result"] == "void"

    def test_resolves_multiple_picks(self):
        stats_provider = MagicMock()
        stats_provider.fetch_player_stats.return_value = [
            PostMatchPlayerStat(player="Judge", market="hits", actual_value=2, confidence="high"),
            PostMatchPlayerStat(player="Soto", market="strikeouts", actual_value=1, confidence="high"),
        ]
        recorder = MagicMock()

        resolver = OutcomeResolver(
            stats_provider=stats_provider, outcome_recorder=recorder
        )
        picks = [
            {"rank": 1, "player": "Judge", "market": "hits", "line": 1.5, "direction": "over"},
            {"rank": 2, "player": "Soto", "market": "strikeouts", "line": 1.5, "direction": "under"},
        ]

        results = resolver.resolve(pick_id="pick-1", picks=picks)

        assert len(results) == 2
        assert results[0]["result"] == "win"
        assert results[1]["result"] == "win"

    def test_handles_match_postponed_as_void(self):
        stats_provider = MagicMock()
        stats_provider.fetch_player_stats.side_effect = ValueError("match_postponed")
        recorder = MagicMock()

        resolver = OutcomeResolver(
            stats_provider=stats_provider, outcome_recorder=recorder
        )
        picks = [{"rank": 1, "player": "Judge", "market": "hits", "line": 1.5, "direction": "over"}]

        results = resolver.resolve(pick_id="pick-1", picks=picks, game_status="postponed")

        assert len(results) == 1
        assert results[0]["result"] == "void"
