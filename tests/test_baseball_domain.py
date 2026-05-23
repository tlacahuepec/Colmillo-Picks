"""Tests for baseball domain model foundation."""

from __future__ import annotations

from baseball_domain import (
    BaseballContext,
    BaseballBatter,
    BaseballPitcher,
    BallparkInfo,
    BaseballProviderStatus,
)
from baseball_module import BaseballModule


class TestBaseballBatterModel:
    def test_batter_has_core_fields(self) -> None:
        batter = BaseballBatter(
            player_name="Aaron Judge",
            team="NYY",
            position="RF",
            handedness="R",
            batting_order=2,
            avg=0.310,
            obp=0.420,
            slg=0.630,
            hits_last5=8,
            total_bases_last5=14,
        )
        assert batter.player_name == "Aaron Judge"
        assert batter.handedness == "R"
        assert batter.batting_order == 2

    def test_batter_optional_fields_default_none(self) -> None:
        batter = BaseballBatter(player_name="Test", team="TST", position="DH")
        assert batter.handedness is None
        assert batter.batting_order is None
        assert batter.avg is None
        assert batter.obp is None
        assert batter.slg is None


class TestBaseballPitcherModel:
    def test_pitcher_has_core_fields(self) -> None:
        pitcher = BaseballPitcher(
            player_name="Gerrit Cole",
            team="NYY",
            handedness="R",
            era=2.95,
            whip=1.05,
            k_per_9=11.5,
            recent_workload_innings=18.0,
            is_starter=True,
        )
        assert pitcher.player_name == "Gerrit Cole"
        assert pitcher.is_starter is True
        assert pitcher.k_per_9 == 11.5

    def test_pitcher_optional_fields_default_none(self) -> None:
        pitcher = BaseballPitcher(player_name="Test", team="TST")
        assert pitcher.handedness is None
        assert pitcher.era is None
        assert pitcher.is_starter is None
        assert pitcher.recent_workload_innings is None


class TestBaseballContext:
    def test_context_supports_batters_and_pitchers(self) -> None:
        ctx = BaseballContext(
            home_team="NYY",
            away_team="BOS",
            match_date="2026-06-01",
            batters=[
                BaseballBatter(player_name="Judge", team="NYY", position="RF"),
            ],
            pitchers=[
                BaseballPitcher(player_name="Cole", team="NYY", is_starter=True),
            ],
        )
        assert len(ctx.batters) == 1
        assert len(ctx.pitchers) == 1
        assert ctx.batters[0].player_name == "Judge"
        assert ctx.pitchers[0].player_name == "Cole"

    def test_context_supports_ballpark(self) -> None:
        park = BallparkInfo(name="Yankee Stadium", park_factor=1.05)
        ctx = BaseballContext(
            home_team="NYY", away_team="BOS", match_date="2026-06-01",
            ballpark=park,
        )
        assert ctx.ballpark is not None
        assert ctx.ballpark.park_factor == 1.05

    def test_context_supports_weather(self) -> None:
        ctx = BaseballContext(
            home_team="NYY", away_team="BOS", match_date="2026-06-01",
            weather={"temp_f": 72, "wind_mph": 8, "wind_dir": "out"},
        )
        assert ctx.weather["temp_f"] == 72


class TestMissingBaseballData:
    def test_missing_lineup_represented_safely(self) -> None:
        batter = BaseballBatter(player_name="Test", team="TST", position="OF")
        assert batter.batting_order is None
        assert batter.in_confirmed_lineup is None

    def test_missing_handedness_represented_safely(self) -> None:
        batter = BaseballBatter(player_name="Test", team="TST", position="OF")
        assert batter.handedness is None
        pitcher = BaseballPitcher(player_name="Test", team="TST")
        assert pitcher.handedness is None

    def test_provider_status_tracks_missing_data(self) -> None:
        status = BaseballProviderStatus(
            lineup="unavailable",
            weather="unavailable",
            stats="ok",
        )
        assert status.lineup == "unavailable"
        assert status.stats == "ok"


class TestBaseballContextWithModule:
    def test_fake_context_feeds_baseball_module(self) -> None:
        module = BaseballModule()
        ctx = BaseballContext(
            home_team="Yankees",
            away_team="Red Sox",
            match_date="2026-06-01",
            batters=[
                BaseballBatter(
                    player_name="Aaron Judge", team="NYY", position="RF",
                    handedness="R", batting_order=2, avg=0.310,
                ),
            ],
            pitchers=[
                BaseballPitcher(
                    player_name="Gerrit Cole", team="NYY",
                    is_starter=True, k_per_9=11.5,
                ),
            ],
        )
        inputs = module.collect_inputs(
            home_team=ctx.home_team,
            away_team=ctx.away_team,
            match_date=ctx.match_date,
        )
        scores = module.score(inputs, markets=("hits",))
        assert len(scores) > 0
