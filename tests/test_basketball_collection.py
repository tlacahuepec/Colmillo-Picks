"""Tests for basketball data collection layer."""

from __future__ import annotations

from basketball_collection import (
    BasketballContext,
    BasketballPlayerContext,
    ProviderStatus,
    collect_basketball_inputs,
)
from basketball_scoring import score_basketball_props


class TestBasketballContextModel:
    def test_context_has_required_fields(self) -> None:
        ctx = BasketballContext(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
            players=[],
            provider_status=ProviderStatus(),
        )
        assert ctx.home_team == "Lakers"
        assert ctx.away_team == "Celtics"
        assert ctx.players == []

    def test_player_context_has_stats(self) -> None:
        player = BasketballPlayerContext(
            player_name="LeBron James",
            position="SF",
            team="LAL",
            minutes_proj=34.0,
            usage_rate=0.28,
            points_avg=25.0,
            points_last5=27.0,
            assist_avg=7.0,
            assist_last5=7.5,
            rebound_avg=7.5,
            rebound_last5=8.0,
            threes_avg=2.5,
            threes_last5=2.8,
            pace_factor=1.02,
            is_starter=True,
        )
        assert player.player_name == "LeBron James"
        assert player.minutes_proj == 34.0
        assert player.is_starter is True


class TestFakeProvidersCollect:
    def test_fake_providers_build_valid_context(self) -> None:
        ctx = collect_basketball_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
            league="nba",
        )
        assert isinstance(ctx, BasketballContext)
        assert ctx.home_team == "Lakers"
        assert ctx.away_team == "Celtics"
        assert len(ctx.players) > 0
        for player in ctx.players:
            assert isinstance(player, BasketballPlayerContext)
            assert player.player_name != ""

    def test_collected_players_have_scoring_data(self) -> None:
        ctx = collect_basketball_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
        )
        player = ctx.players[0]
        assert player.minutes_proj is not None
        assert player.points_avg is not None


class TestMissingProviderData:
    def test_missing_injury_data_marked_unavailable(self) -> None:
        ctx = collect_basketball_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
            injuries_available=False,
        )
        assert ctx.provider_status.injuries == "unavailable"

    def test_missing_lineup_data_marked_unavailable(self) -> None:
        ctx = collect_basketball_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
            lineups_available=False,
        )
        assert ctx.provider_status.lineups == "unavailable"

    def test_all_providers_available_by_default(self) -> None:
        ctx = collect_basketball_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
        )
        assert ctx.provider_status.injuries == "ok"
        assert ctx.provider_status.lineups == "ok"
        assert ctx.provider_status.stats == "ok"


class TestScorerConsumesCollectedData:
    def test_basketball_scorer_accepts_collected_context(self) -> None:
        ctx = collect_basketball_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
        )
        player_dicts = [p.to_scoring_dict() for p in ctx.players]
        scores = score_basketball_props(player_dicts, markets=("points", "assists"))
        assert len(scores) > 0
        for pick in scores:
            assert "player" in pick
            assert "market" in pick
            assert "score" in pick

    def test_missing_data_players_still_score(self) -> None:
        ctx = collect_basketball_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
            injuries_available=False,
        )
        player_dicts = [p.to_scoring_dict() for p in ctx.players]
        scores = score_basketball_props(player_dicts, markets=("points",))
        assert len(scores) > 0
