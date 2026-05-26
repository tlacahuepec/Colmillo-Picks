"""Tests for MLB provider port protocols (S05)."""

from __future__ import annotations

from mlb_provider_ports import (
    MLBProviderMeta,
    MLBScheduleResult,
    ProbablePitcherResult,
    MLBLineupsResult,
    MLBPlayerStatsResult,
    SplitsResult,
    BullpenResult,
    MLBWeatherResult,
    BallparkResult,
    MLBSchedulePort,
    ProbablePitcherPort,
    MLBLineupsPort,
    MLBPlayerStatsPort,
    PlayerSplitsPort,
    BullpenPort,
    MLBWeatherPort,
    BallparkPort,
)


class FakeScheduleProvider:
    def get_schedule(self, *, date: str, team_id: int | None = None) -> MLBScheduleResult:
        return MLBScheduleResult(
            meta=MLBProviderMeta(available=True, source="fake"),
            games=[{"game_pk": 717001, "home": "NYY", "away": "BOS"}],
        )


class FakePitcherProvider:
    def get_probable_pitchers(self, *, game_pk: int) -> ProbablePitcherResult:
        return ProbablePitcherResult(
            meta=MLBProviderMeta(available=True, source="fake"),
            home_pitcher={"name": "Cole", "id": 543037},
            away_pitcher={"name": "Sale", "id": 519242},
        )


class FakeLineupsProvider:
    def get_lineups(self, *, game_pk: int) -> MLBLineupsResult:
        return MLBLineupsResult(
            meta=MLBProviderMeta(available=True, source="fake"),
            home_order=[{"position": 1, "name": "Judge"}],
            away_order=[{"position": 1, "name": "Devers"}],
            confirmed=True,
        )


class FakePlayerStatsProvider:
    def get_player_stats(self, *, player_id: int, season: int | None = None) -> MLBPlayerStatsResult:
        return MLBPlayerStatsResult(
            meta=MLBProviderMeta(available=True, source="fake"),
            player_id=player_id,
            season_stats={"avg": 0.310, "hr": 25},
        )


class FakeSplitsProvider:
    def get_splits(self, *, player_id: int, season: int | None = None) -> SplitsResult:
        return SplitsResult(
            meta=MLBProviderMeta(available=True, source="fake"),
            splits={"vs_lhp": {"avg": 0.320}, "vs_rhp": {"avg": 0.290}},
        )


class FakeBullpenProvider:
    def get_bullpen_state(self, *, team_id: int, date: str) -> BullpenResult:
        return BullpenResult(
            meta=MLBProviderMeta(available=True, source="fake"),
            arms=[{"name": "Holmes", "available": True}],
        )


class FakeWeatherProvider:
    def get_weather(self, *, game_pk: int, game_time_utc: str) -> MLBWeatherResult:
        return MLBWeatherResult(
            meta=MLBProviderMeta(available=True, source="fake"),
            temp_f=75,
            wind_mph=8,
            wind_direction="out_to_cf",
        )


class FakeBallparkProvider:
    def get_ballpark(self, *, venue_id: int) -> BallparkResult:
        return BallparkResult(
            meta=MLBProviderMeta(available=True, source="fake"),
            park_factor=1.05,
            venue_name="Yankee Stadium",
        )


class TestMLBPortProtocols:
    def test_schedule_port_satisfied(self) -> None:
        assert isinstance(FakeScheduleProvider(), MLBSchedulePort)

    def test_pitcher_port_satisfied(self) -> None:
        assert isinstance(FakePitcherProvider(), ProbablePitcherPort)

    def test_lineups_port_satisfied(self) -> None:
        assert isinstance(FakeLineupsProvider(), MLBLineupsPort)

    def test_player_stats_port_satisfied(self) -> None:
        assert isinstance(FakePlayerStatsProvider(), MLBPlayerStatsPort)

    def test_splits_port_satisfied(self) -> None:
        assert isinstance(FakeSplitsProvider(), PlayerSplitsPort)

    def test_bullpen_port_satisfied(self) -> None:
        assert isinstance(FakeBullpenProvider(), BullpenPort)

    def test_weather_port_satisfied(self) -> None:
        assert isinstance(FakeWeatherProvider(), MLBWeatherPort)

    def test_ballpark_port_satisfied(self) -> None:
        assert isinstance(FakeBallparkProvider(), BallparkPort)


class TestMLBResultDefaults:
    def test_meta_defaults_unavailable(self) -> None:
        meta = MLBProviderMeta()
        assert meta.available is False
        assert meta.provider_status == "unavailable"
        assert meta.source == "unknown"

    def test_schedule_result_default_empty(self) -> None:
        result = MLBScheduleResult()
        assert result.games == []
        assert result.meta.available is False

    def test_lineups_result_default_unconfirmed(self) -> None:
        result = MLBLineupsResult()
        assert result.confirmed is False
        assert result.home_order == []

    def test_ballpark_result_default_factor(self) -> None:
        result = BallparkResult()
        assert result.park_factor == 1.0
        assert result.hr_factor is None


class TestExistingPortsUnchanged:
    def test_existing_provider_ports_importable(self) -> None:
        from provider_ports import (
            EventLookupPort,
            OddsPort,
            PlayerStatsPort,
            InjuryReportPort,
            LineupsPort,
            PropLinesPort,
        )
        assert EventLookupPort is not None
        assert OddsPort is not None
        assert PlayerStatsPort is not None
        assert InjuryReportPort is not None
        assert LineupsPort is not None
        assert PropLinesPort is not None
