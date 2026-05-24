"""Tests for basketball data collection layer."""

from __future__ import annotations

from basketball_collection import (
    BasketballContext,
    BasketballGameContext,
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


class TestBasketballGameContext:
    def test_game_context_defaults(self) -> None:
        ctx = BasketballGameContext(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
        )
        assert ctx.league == "nba"
        assert ctx.is_playoff is False
        assert ctx.tipoff_utc is None
        assert ctx.home_pace is None
        assert ctx.spread is None

    def test_game_context_with_full_data(self) -> None:
        ctx = BasketballGameContext(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
            tipoff_utc="2026-06-01T19:30:00Z",
            home_pace=100.5,
            away_pace=98.2,
            projected_game_pace=99.3,
            home_defensive_rating=112.0,
            away_defensive_rating=108.5,
            home_win_prob=0.55,
            away_win_prob=0.45,
            over_under_total=224.5,
            spread=-3.5,
            home_rest_days=2,
            away_rest_days=1,
            is_playoff=True,
            series_game_number=3,
            venue="Crypto.com Arena",
        )
        assert ctx.projected_game_pace == 99.3
        assert ctx.is_playoff is True
        assert ctx.series_game_number == 3
        assert ctx.venue == "Crypto.com Arena"


class TestExpandedPlayerContext:
    def test_new_fields_default_to_none(self) -> None:
        player = BasketballPlayerContext(
            player_name="Test", position="PG", team="TST",
        )
        assert player.rotation_risk is None
        assert player.rest_days is None
        assert player.home_away is None
        assert player.usage_boost is None
        assert player.opp_points_rank is None
        assert player.opp_assist_rank is None
        assert player.opp_three_rank is None
        assert player.three_point_attempts is None
        assert player.market_agreement is None

    def test_to_scoring_dict_includes_new_fields(self) -> None:
        player = BasketballPlayerContext(
            player_name="Luka Doncic", position="PG", team="DAL",
            minutes_proj=36.0, usage_rate=0.33,
            rest_days=2, home_away="home", rotation_risk="locked_in",
            opp_points_rank=25, opp_assist_rank=20, opp_three_rank=18,
            usage_boost=0.05, market_agreement=0.85,
            three_point_attempts=8.5,
        )
        d = player.to_scoring_dict()
        assert d["rest_days"] == 2
        assert d["home_away"] == "home"
        assert d["rotation_risk"] == "locked_in"
        assert d["opp_points_rank"] == 25
        assert d["opp_assist_rank"] == 20
        assert d["opp_three_rank"] == 18
        assert d["usage_boost"] == 0.05
        assert d["market_agreement"] == 0.85
        assert d["three_point_attempts"] == 8.5

    def test_to_scoring_dict_omits_none_fields(self) -> None:
        player = BasketballPlayerContext(
            player_name="Test", position="SF", team="TST",
            minutes_proj=30.0,
        )
        d = player.to_scoring_dict()
        assert "rest_days" not in d
        assert "home_away" not in d
        assert "rotation_risk" not in d
        assert "minutes_proj" in d
