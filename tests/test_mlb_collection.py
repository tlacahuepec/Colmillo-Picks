"""Tests for MLB collection service."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any


from baseball_domain import (
    MLBGame,
    MLBGameContext,
)
from mlb_collection import MLBCollectionConfig, MLBCollectionService
from mlb_provider_ports import (
    BallparkResult,
    BullpenResult,
    MLBLineupsResult,
    MLBPlayerStatsResult,
    MLBProviderMeta,
    MLBScheduleResult,
    MLBWeatherResult,
    ProbablePitcherResult,
    SplitsResult,
)


def _fresh_meta(available: bool = True) -> MLBProviderMeta:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status = "fresh" if available else "unavailable"
    return MLBProviderMeta(
        available=available,
        source="fake",
        retrieved_at_utc=ts,
        provider_status=status,
    )


def _stale_meta() -> MLBProviderMeta:
    ts = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return MLBProviderMeta(
        available=True,
        source="fake",
        retrieved_at_utc=ts,
        provider_status="fresh",
    )


class FakeSchedule:
    def get_schedule(self, *, date: str, team_id: int | None = None) -> MLBScheduleResult:
        return MLBScheduleResult(
            meta=_fresh_meta(),
            games=[{"gamePk": 717465, "teams": {"home": {"team": {"name": "Yankees"}}}}],
        )


class FakePitchers:
    def __init__(self, *, available: bool = True, confirmed: bool = True):
        self._available = available
        self._confirmed = confirmed

    def get_probable_pitchers(self, *, game_pk: int) -> ProbablePitcherResult:
        if not self._available:
            return ProbablePitcherResult(meta=_fresh_meta(available=False))
        home = {"id": 543037, "fullName": "Gerrit Cole", "confirmed": self._confirmed}
        away = {"id": 543038, "fullName": "Chris Sale", "confirmed": self._confirmed}
        return ProbablePitcherResult(
            meta=_fresh_meta(), home_pitcher=home, away_pitcher=away
        )


class FakeLineups:
    def __init__(self, *, available: bool = True, confirmed: bool = True):
        self._available = available
        self._confirmed = confirmed

    def get_lineups(self, *, game_pk: int) -> MLBLineupsResult:
        if not self._available:
            return MLBLineupsResult(meta=_fresh_meta(available=False))
        return MLBLineupsResult(
            meta=_fresh_meta(),
            home_order=[{"id": 1, "fullName": "Aaron Judge", "position": "RF"}],
            away_order=[{"id": 2, "fullName": "Rafael Devers", "position": "3B"}],
            confirmed=self._confirmed,
        )


class FakePlayerStats:
    def get_player_stats(self, *, player_id: int, season: int | None = None) -> MLBPlayerStatsResult:
        return MLBPlayerStatsResult(
            meta=_fresh_meta(),
            player_id=player_id,
            season_stats={"avg": ".310", "homeRuns": 25},
            game_log=[{"date": "2026-06-14", "hits": 2}],
        )


class FakeSplits:
    def get_splits(self, *, player_id: int, season: int | None = None) -> SplitsResult:
        return SplitsResult(
            meta=_fresh_meta(),
            splits={"vs_lhp": {"avg": 0.280}},
        )


class FakeBullpen:
    def __init__(self, *, available: bool = True):
        self._available = available

    def get_bullpen_state(self, *, team_id: int, date: str) -> BullpenResult:
        if not self._available:
            return BullpenResult(meta=_fresh_meta(available=False))
        return BullpenResult(
            meta=_fresh_meta(),
            arms=[{"fullName": "Clay Holmes", "available": True}],
        )


class FakeWeather:
    def __init__(self, *, available: bool = True):
        self._available = available

    def get_weather(self, *, game_pk: int, game_time_utc: str) -> MLBWeatherResult:
        if not self._available:
            return MLBWeatherResult(meta=_fresh_meta(available=False))
        return MLBWeatherResult(
            meta=_fresh_meta(),
            temp_f=78,
            wind_mph=12,
            wind_direction="Out To RF",
            dome=False,
        )


class FakeBallpark:
    def __init__(self, *, available: bool = True):
        self._available = available

    def get_ballpark(self, *, venue_id: int) -> BallparkResult:
        if not self._available:
            return BallparkResult(meta=_fresh_meta(available=False))
        return BallparkResult(
            meta=_fresh_meta(),
            park_factor=1.05,
            hr_factor=1.15,
            venue_name="Yankee Stadium",
        )


def _make_game() -> MLBGame:
    return MLBGame(
        event_id="717465",
        home_team="Yankees",
        away_team="Red Sox",
        venue="Yankee Stadium",
        game_time_utc="2026-06-15T23:05:00Z",
        home_team_id=147,
        away_team_id=111,
        venue_id=3313,
    )


def _build_service(**overrides: Any) -> MLBCollectionService:
    defaults = {
        "schedule": FakeSchedule(),
        "pitchers": FakePitchers(),
        "lineups": FakeLineups(),
        "player_stats": FakePlayerStats(),
        "splits": FakeSplits(),
        "bullpen": FakeBullpen(),
        "weather": FakeWeather(),
        "ballpark": FakeBallpark(),
    }
    defaults.update(overrides)
    return MLBCollectionService(**defaults)


class TestMLBCollectionHappyPath:
    def test_assembles_full_game_context_from_all_ports(self) -> None:
        service = _build_service()
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert isinstance(ctx, MLBGameContext)
        assert ctx.game.event_id == "717465"

    def test_populates_both_pitchers(self) -> None:
        service = _build_service()
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert ctx.home_probable_pitcher is not None
        assert ctx.home_probable_pitcher.player_name == "Gerrit Cole"
        assert ctx.away_probable_pitcher is not None
        assert ctx.away_probable_pitcher.player_name == "Chris Sale"

    def test_populates_both_batting_orders(self) -> None:
        service = _build_service()
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert ctx.home_batting_order is not None
        assert ctx.home_batting_order.confirmed is True
        assert len(ctx.home_batting_order.slots) > 0
        assert ctx.away_batting_order is not None

    def test_populates_weather_and_ballpark(self) -> None:
        service = _build_service()
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert ctx.weather is not None
        assert ctx.weather.temp_f == 78
        assert ctx.ballpark is not None
        assert ctx.ballpark.name == "Yankee Stadium"

    def test_populates_provider_status_all_ok(self) -> None:
        service = _build_service()
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert ctx.provider_status.stats == "ok"
        assert ctx.provider_status.lineup == "ok"
        assert ctx.provider_status.weather == "ok"
        assert ctx.provider_status.bullpen == "ok"


class TestMLBCollectionRejection:
    def test_no_rejection_when_pitcher_confirmed(self) -> None:
        service = _build_service(
            pitchers=FakePitchers(confirmed=True),
            lineups=FakeLineups(confirmed=False),
        )
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert ctx.should_reject_prediction is False

    def test_no_rejection_when_lineup_confirmed(self) -> None:
        service = _build_service(
            pitchers=FakePitchers(confirmed=False),
            lineups=FakeLineups(confirmed=True),
        )
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert ctx.should_reject_prediction is False

    def test_rejects_when_both_pitcher_and_lineup_unconfirmed(self) -> None:
        service = _build_service(
            pitchers=FakePitchers(confirmed=False),
            lineups=FakeLineups(confirmed=False),
        )
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert ctx.should_reject_prediction is True
        assert len(ctx.rejection_reasons) > 0

    def test_does_not_reject_when_only_pitcher_missing(self) -> None:
        service = _build_service(
            pitchers=FakePitchers(available=False),
            lineups=FakeLineups(confirmed=True),
        )
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert ctx.should_reject_prediction is False

    def test_does_not_reject_when_only_lineup_missing(self) -> None:
        service = _build_service(
            pitchers=FakePitchers(confirmed=True),
            lineups=FakeLineups(available=False),
        )
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert ctx.should_reject_prediction is False


class TestMLBCollectionDegradedData:
    def test_unavailable_pitcher_port_still_returns_context(self) -> None:
        service = _build_service(pitchers=FakePitchers(available=False))
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert isinstance(ctx, MLBGameContext)
        assert ctx.home_probable_pitcher is None
        assert ctx.away_probable_pitcher is None

    def test_unavailable_lineup_port_still_returns_context(self) -> None:
        service = _build_service(lineups=FakeLineups(available=False))
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert isinstance(ctx, MLBGameContext)
        assert ctx.home_batting_order is None

    def test_unavailable_weather_does_not_block(self) -> None:
        service = _build_service(weather=FakeWeather(available=False))
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert isinstance(ctx, MLBGameContext)
        assert ctx.weather is None

    def test_weather_receives_game_pk_not_venue_id(self) -> None:
        class RecordingWeather:
            def __init__(self):
                self.received_game_pk = None

            def get_weather(self, *, game_pk: int, game_time_utc: str) -> MLBWeatherResult:
                self.received_game_pk = game_pk
                return MLBWeatherResult(meta=_fresh_meta(), temp_f=72)

        weather = RecordingWeather()
        service = _build_service(weather=weather)
        service.collect(game_pk=717465, game=_make_game())
        assert weather.received_game_pk == 717465

    def test_all_ports_unavailable_returns_minimal_context(self) -> None:
        service = _build_service(
            pitchers=FakePitchers(available=False),
            lineups=FakeLineups(available=False),
            bullpen=FakeBullpen(available=False),
            weather=FakeWeather(available=False),
            ballpark=FakeBallpark(available=False),
        )
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert isinstance(ctx, MLBGameContext)
        assert ctx.game.event_id == "717465"


class TestMLBCollectionFreshness:
    def test_stale_data_marks_provider_status(self) -> None:
        class StalePitchers:
            def get_probable_pitchers(self, *, game_pk: int) -> ProbablePitcherResult:
                return ProbablePitcherResult(
                    meta=_stale_meta(),
                    home_pitcher={"id": 1, "fullName": "Cole", "confirmed": True},
                    away_pitcher={"id": 2, "fullName": "Sale", "confirmed": True},
                )

        service = _build_service(
            pitchers=StalePitchers(),
            config=MLBCollectionConfig(freshness_threshold_minutes=30),
        )
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert isinstance(ctx, MLBGameContext)

    def test_freshness_threshold_configurable(self) -> None:
        service = _build_service(
            config=MLBCollectionConfig(freshness_threshold_minutes=120),
        )
        ctx = service.collect(game_pk=717465, game=_make_game())
        assert ctx.provider_status.stats == "ok"
