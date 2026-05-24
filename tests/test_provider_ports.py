"""Tests for shared multi-sport provider interfaces."""

from __future__ import annotations

from provider_ports import (
    EventLookupPort,
    EventResult,
    InjuryReportPort,
    InjuryResult,
    LineupsPort,
    LineupsResult,
    OddsPort,
    OddsResult,
    PlayerStatsPort,
    PlayerStatsResult,
    PropLinesPort,
    PropLinesResult,
    ProviderUnavailableResult,
)


class FakeEventLookup:
    def lookup_event(self, *, sport: str, home_team: str, away_team: str, event_date: str, league: str | None = None) -> EventResult:
        return EventResult(
            found=True,
            event_id="EVT-123",
            home_team=home_team,
            away_team=away_team,
            event_date=event_date,
            venue="Test Stadium",
        )


class FakeOdds:
    def get_odds(self, *, sport: str, event_id: str) -> OddsResult:
        return OddsResult(
            available=True,
            home_win_prob=0.45,
            away_win_prob=0.35,
            draw_prob=0.20,
        )


class FakePlayerStats:
    def get_player_stats(self, *, sport: str, player_id: str, league: str | None = None) -> PlayerStatsResult:
        return PlayerStatsResult(
            available=True,
            player_id=player_id,
            stats={"passes_avg": 55.0, "shots_avg": 3.2},
        )


class FakeInjuryReport:
    def get_injuries(self, *, sport: str, team_id: str) -> InjuryResult:
        return InjuryResult(
            available=True,
            injuries=[{"player": "P1", "status": "doubtful", "reason": "hamstring"}],
        )


class FakeLineups:
    def get_lineups(self, *, sport: str, event_id: str) -> LineupsResult:
        return LineupsResult(
            available=True,
            status="confirmed",
            players=["P1", "P2", "P3"],
        )


class FakePropLines:
    def get_prop_lines(self, *, sport: str, event_id: str, markets: tuple[str, ...] = ()) -> PropLinesResult:
        return PropLinesResult(
            available=True,
            lines=[{"player": "P1", "market": "passes", "line": 55.5}],
        )


class TestProviderProtocolConformance:
    def test_event_lookup_satisfies_protocol(self) -> None:
        provider = FakeEventLookup()
        assert isinstance(provider, EventLookupPort)

    def test_odds_satisfies_protocol(self) -> None:
        provider = FakeOdds()
        assert isinstance(provider, OddsPort)

    def test_player_stats_satisfies_protocol(self) -> None:
        provider = FakePlayerStats()
        assert isinstance(provider, PlayerStatsPort)

    def test_injury_report_satisfies_protocol(self) -> None:
        provider = FakeInjuryReport()
        assert isinstance(provider, InjuryReportPort)

    def test_lineups_satisfies_protocol(self) -> None:
        provider = FakeLineups()
        assert isinstance(provider, LineupsPort)

    def test_prop_lines_satisfies_protocol(self) -> None:
        provider = FakePropLines()
        assert isinstance(provider, PropLinesPort)


class TestProviderOutputModels:
    def test_event_result_fields(self) -> None:
        result = FakeEventLookup().lookup_event(
            sport="soccer", home_team="A", away_team="B", event_date="2026-06-01"
        )
        assert result.found is True
        assert result.event_id == "EVT-123"
        assert result.home_team == "A"

    def test_odds_result_fields(self) -> None:
        result = FakeOdds().get_odds(sport="soccer", event_id="EVT-123")
        assert result.available is True
        assert result.home_win_prob == 0.45

    def test_player_stats_result_fields(self) -> None:
        result = FakePlayerStats().get_player_stats(sport="soccer", player_id="P1")
        assert result.available is True
        assert result.stats["passes_avg"] == 55.0


class TestMissingProviderData:
    def test_event_not_found(self) -> None:
        result = EventResult(found=False)
        assert result.found is False
        assert result.event_id is None

    def test_odds_unavailable(self) -> None:
        result = OddsResult(available=False)
        assert result.available is False
        assert result.home_win_prob is None

    def test_provider_unavailable_result(self) -> None:
        result = ProviderUnavailableResult(reason="API key missing")
        assert result.available is False
        assert result.reason == "API key missing"
