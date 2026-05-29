"""Tests for baseball domain model foundation."""

from __future__ import annotations

from baseball_domain import (
    BaseballContext,
    BaseballBatter,
    BaseballPitcher,
    BallparkInfo,
    BaseballProviderStatus,
    MLBGame,
    MLBProbablePitcher,
    MLBBattingOrder,
    MLBBattingOrderSlot,
    MLBBullpenArm,
    MLBBullpenState,
    MLBWeather,
    MLBPropLine,
    MLBPlayerSplits,
    MLBGameContext,
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
        module = BaseballModule(allow_deterministic_fallback=True)
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


class TestMLBGame:
    def test_minimal_game(self) -> None:
        game = MLBGame(
            event_id="717001",
            home_team="NYY",
            away_team="BOS",
            venue="Yankee Stadium",
            game_time_utc="2026-06-15T23:05:00Z",
        )
        assert game.status == "scheduled"
        assert game.double_header is False
        assert game.game_number == 1

    def test_doubleheader_game(self) -> None:
        game = MLBGame(
            event_id="717002",
            home_team="NYY",
            away_team="BOS",
            venue="Yankee Stadium",
            game_time_utc="2026-06-15T17:05:00Z",
            double_header=True,
            game_number=1,
        )
        assert game.double_header is True
        assert game.game_number == 1

    def test_game_with_team_ids(self) -> None:
        game = MLBGame(
            event_id="717003",
            home_team="NYY",
            away_team="BOS",
            venue="Yankee Stadium",
            game_time_utc="2026-06-15T23:05:00Z",
            home_team_id=147,
            away_team_id=111,
            venue_id=3313,
        )
        assert game.home_team_id == 147
        assert game.away_team_id == 111
        assert game.venue_id == 3313


class TestMLBProbablePitcher:
    def test_unconfirmed_default(self) -> None:
        pitcher = MLBProbablePitcher(player_name="Gerrit Cole")
        assert pitcher.confirmed is False
        assert pitcher.player_id is None
        assert pitcher.era is None

    def test_full_stats(self) -> None:
        pitcher = MLBProbablePitcher(
            player_name="Gerrit Cole",
            player_id=543037,
            team="NYY",
            handedness="R",
            confirmed=True,
            era=2.95,
            whip=1.05,
            k_per_9=11.5,
            bb_per_9=2.1,
            innings_pitched_season=95.2,
            last_start_date="2026-06-10",
            days_rest=5,
        )
        assert pitcher.confirmed is True
        assert pitcher.k_per_9 == 11.5
        assert pitcher.days_rest == 5


class TestMLBBattingOrder:
    def test_empty_order(self) -> None:
        order = MLBBattingOrder(team="NYY")
        assert order.confirmed is False
        assert order.slots == []

    def test_with_slots(self) -> None:
        slots = [
            MLBBattingOrderSlot(position=1, player_name="Torres", handedness="R", field_position="2B"),
            MLBBattingOrderSlot(position=2, player_name="Judge", handedness="R", field_position="RF"),
        ]
        order = MLBBattingOrder(team="NYY", confirmed=True, slots=slots)
        assert order.confirmed is True
        assert len(order.slots) == 2
        assert order.slots[0].position == 1


class TestMLBBullpenState:
    def test_available_and_unavailable_arms(self) -> None:
        arms = [
            MLBBullpenArm(player_name="Holmes", available=True, days_since_last_appearance=2),
            MLBBullpenArm(player_name="Weaver", available=False, innings_last_3_days=4.0),
        ]
        bullpen = MLBBullpenState(team="NYY", arms=arms)
        assert bullpen.arms[0].available is True
        assert bullpen.arms[1].available is False
        assert bullpen.arms[1].innings_last_3_days == 4.0


class TestMLBWeather:
    def test_dome_stadium(self) -> None:
        weather = MLBWeather(dome=True)
        assert weather.dome is True
        assert weather.temp_f is None

    def test_outdoor_with_wind(self) -> None:
        weather = MLBWeather(
            temp_f=78,
            wind_mph=12,
            wind_direction="out_to_cf",
            humidity_pct=55,
            dome=False,
            source="weather_api",
        )
        assert weather.wind_direction == "out_to_cf"
        assert weather.source == "weather_api"


class TestMLBPropLine:
    def test_user_input_default_source(self) -> None:
        line = MLBPropLine(player_name="Judge", market="hits", line=1.5)
        assert line.source == "user_input"
        assert line.over_odds is None

    def test_with_odds(self) -> None:
        line = MLBPropLine(
            player_name="Judge",
            market="home_runs",
            line=0.5,
            over_odds=-130,
            under_odds=110,
            source="prizepicks",
        )
        assert line.over_odds == -130
        assert line.source == "prizepicks"


class TestMLBPlayerSplits:
    def test_empty_defaults(self) -> None:
        splits = MLBPlayerSplits(player_name="Judge")
        assert splits.vs_lhp == {}
        assert splits.home == {}
        assert splits.last_7_days == {}

    def test_populated_splits(self) -> None:
        splits = MLBPlayerSplits(
            player_name="Judge",
            player_id=592450,
            vs_lhp={"avg": 0.320, "hr_rate": 0.08},
            vs_rhp={"avg": 0.290, "hr_rate": 0.06},
            home={"avg": 0.310},
            last_7_days={"avg": 0.400, "hits_per_game": 1.8},
        )
        assert splits.vs_lhp["avg"] == 0.320
        assert splits.last_7_days["hits_per_game"] == 1.8


class TestMLBGameContext:
    def test_full_composition(self) -> None:
        game = MLBGame(
            event_id="717001",
            home_team="NYY",
            away_team="BOS",
            venue="Yankee Stadium",
            game_time_utc="2026-06-15T23:05:00Z",
        )
        ctx = MLBGameContext(
            game=game,
            home_probable_pitcher=MLBProbablePitcher(player_name="Cole", confirmed=True),
            away_probable_pitcher=MLBProbablePitcher(player_name="Sale"),
            home_batting_order=MLBBattingOrder(team="NYY", confirmed=True),
            weather=MLBWeather(temp_f=75, wind_mph=8),
            ballpark=BallparkInfo(name="Yankee Stadium", park_factor=1.05),
            prop_lines=[MLBPropLine(player_name="Judge", market="hits", line=1.5)],
        )
        assert ctx.home_probable_pitcher.confirmed is True
        assert ctx.weather.temp_f == 75
        assert len(ctx.prop_lines) == 1

    def test_minimal_context(self) -> None:
        game = MLBGame(
            event_id="717001",
            home_team="NYY",
            away_team="BOS",
            venue="Yankee Stadium",
            game_time_utc="2026-06-15T23:05:00Z",
        )
        ctx = MLBGameContext(game=game)
        assert ctx.home_probable_pitcher is None
        assert ctx.prop_lines == []
        assert ctx.should_reject_prediction is False

    def test_rejection_flags(self) -> None:
        game = MLBGame(
            event_id="717001",
            home_team="NYY",
            away_team="BOS",
            venue="Yankee Stadium",
            game_time_utc="2026-06-15T23:05:00Z",
        )
        ctx = MLBGameContext(
            game=game,
            should_reject_prediction=True,
            rejection_reasons=["no confirmed starter", "lineup unavailable"],
        )
        assert ctx.should_reject_prediction is True
        assert len(ctx.rejection_reasons) == 2
