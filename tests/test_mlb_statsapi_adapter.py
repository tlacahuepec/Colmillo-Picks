"""Tests for MLB-StatsAPI adapter implementations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from mlb_provider_ports import (
    BallparkPort,
    BallparkResult,
    BullpenPort,
    BullpenResult,
    MLBLineupsPort,
    MLBLineupsResult,
    MLBPlayerStatsPort,
    MLBPlayerStatsResult,
    MLBSchedulePort,
    MLBScheduleResult,
    MLBWeatherPort,
    MLBWeatherResult,
    PlayerSplitsPort,
    ProbablePitcherPort,
    ProbablePitcherResult,
    SplitsResult,
)
from mlb_statsapi_adapter import (
    StatsAPIBallparkAdapter,
    StatsAPIBullpenAdapter,
    StatsAPIConfig,
    StatsAPILineupsAdapter,
    StatsAPIPlayerStatsAdapter,
    StatsAPIPitcherAdapter,
    StatsAPIScheduleAdapter,
    StatsAPISplitsAdapter,
    StatsAPIWeatherAdapter,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mlb"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


def _mock_client(fixture_name: str, status_code: int = 200) -> httpx.Client:
    data = _load_fixture(fixture_name)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=data)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _error_client(status_code: int = 500) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"message": "error"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _timeout_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connection timed out")

    return httpx.Client(transport=httpx.MockTransport(handler))


class TestStatsAPIScheduleAdapter:
    def test_satisfies_protocol(self) -> None:
        adapter = StatsAPIScheduleAdapter(client=_mock_client("schedule.json"))
        assert isinstance(adapter, MLBSchedulePort)

    def test_parses_schedule_response(self) -> None:
        adapter = StatsAPIScheduleAdapter(client=_mock_client("schedule.json"))
        result = adapter.get_schedule(date="2026-06-15")
        assert result.meta.available is True
        assert result.meta.source == "mlb-statsapi"
        assert len(result.games) == 1
        game = result.games[0]
        assert game["gamePk"] == 717465
        assert game["teams"]["home"]["team"]["name"] == "New York Yankees"

    def test_filters_by_team_id(self) -> None:
        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_made.append(request)
            data = _load_fixture("schedule.json")
            return httpx.Response(200, json=data)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIScheduleAdapter(client=client)
        adapter.get_schedule(date="2026-06-15", team_id=147)
        assert "teamId=147" in str(requests_made[0].url)

    def test_returns_unavailable_on_network_error(self) -> None:
        adapter = StatsAPIScheduleAdapter(
            client=_timeout_client(),
            config=StatsAPIConfig(max_retries=0),
        )
        result = adapter.get_schedule(date="2026-06-15")
        assert result.meta.available is False
        assert result.meta.error_message is not None

    def test_returns_unavailable_on_empty_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"dates": []})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIScheduleAdapter(client=client)
        result = adapter.get_schedule(date="2026-06-15")
        assert result.meta.available is True
        assert len(result.games) == 0

    def test_never_raises(self) -> None:
        adapter = StatsAPIScheduleAdapter(
            client=_error_client(500),
            config=StatsAPIConfig(max_retries=0),
        )
        result = adapter.get_schedule(date="2026-06-15")
        assert isinstance(result, MLBScheduleResult)


class TestStatsAPIPitcherAdapter:
    def test_satisfies_protocol(self) -> None:
        adapter = StatsAPIPitcherAdapter(client=_mock_client("schedule_with_pitchers.json"))
        assert isinstance(adapter, ProbablePitcherPort)

    def test_parses_probable_pitchers(self) -> None:
        adapter = StatsAPIPitcherAdapter(client=_mock_client("schedule_with_pitchers.json"))
        result = adapter.get_probable_pitchers(game_pk=717465)
        assert result.meta.available is True
        assert result.home_pitcher is not None
        assert result.home_pitcher["fullName"] == "Gerrit Cole"
        assert result.away_pitcher is not None
        assert result.away_pitcher["fullName"] == "Chris Sale"

    def test_unannounced_pitcher_returns_none(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            data = _load_fixture("schedule.json")
            return httpx.Response(200, json=data)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIPitcherAdapter(client=client)
        result = adapter.get_probable_pitchers(game_pk=717465)
        assert result.meta.available is True
        assert result.home_pitcher is None
        assert result.away_pitcher is None

    def test_never_raises_on_malformed_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"unexpected": "format"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIPitcherAdapter(client=client)
        result = adapter.get_probable_pitchers(game_pk=717465)
        assert isinstance(result, ProbablePitcherResult)


class TestStatsAPILineupsAdapter:
    def test_satisfies_protocol(self) -> None:
        adapter = StatsAPILineupsAdapter(client=_mock_client("game_feed_live.json"))
        assert isinstance(adapter, MLBLineupsPort)

    def test_parses_confirmed_lineup(self) -> None:
        adapter = StatsAPILineupsAdapter(client=_mock_client("game_feed_live.json"))
        result = adapter.get_lineups(game_pk=717465)
        assert result.meta.available is True
        assert result.confirmed is True
        assert len(result.home_order) == 9
        assert len(result.away_order) == 9
        assert result.home_order[0]["fullName"] == "Juan Soto"
        assert result.away_order[0]["fullName"] == "Jarren Duran"

    def test_unconfirmed_lineup_when_game_not_started(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            data = _load_fixture("game_feed_live.json")
            data["gameData"]["status"]["abstractGameState"] = "Preview"
            data["liveData"]["boxscore"]["teams"]["home"]["battingOrder"] = []
            data["liveData"]["boxscore"]["teams"]["away"]["battingOrder"] = []
            return httpx.Response(200, json=data)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPILineupsAdapter(client=client)
        result = adapter.get_lineups(game_pk=717465)
        assert result.confirmed is False

    def test_never_raises_on_500(self) -> None:
        adapter = StatsAPILineupsAdapter(
            client=_error_client(500),
            config=StatsAPIConfig(max_retries=0),
        )
        result = adapter.get_lineups(game_pk=717465)
        assert isinstance(result, MLBLineupsResult)
        assert result.meta.available is False


class TestStatsAPIPlayerStatsAdapter:
    def test_satisfies_protocol(self) -> None:
        adapter = StatsAPIPlayerStatsAdapter(client=_mock_client("player_stats_batter.json"))
        assert isinstance(adapter, MLBPlayerStatsPort)

    def test_parses_season_stats(self) -> None:
        adapter = StatsAPIPlayerStatsAdapter(client=_mock_client("player_stats_batter.json"))
        result = adapter.get_player_stats(player_id=592450)
        assert result.meta.available is True
        assert result.player_id == 592450
        assert result.season_stats["avg"] == ".318"
        assert result.season_stats["homeRuns"] == 25

    def test_parses_game_log(self) -> None:
        adapter = StatsAPIPlayerStatsAdapter(client=_mock_client("player_stats_batter.json"))
        result = adapter.get_player_stats(player_id=592450)
        assert len(result.game_log) == 3
        assert result.game_log[0]["date"] == "2026-06-14"

    def test_never_raises_on_invalid_player_id(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"message": "Not Found"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIPlayerStatsAdapter(
            client=client,
            config=StatsAPIConfig(max_retries=0),
        )
        result = adapter.get_player_stats(player_id=999999)
        assert isinstance(result, MLBPlayerStatsResult)
        assert result.meta.available is False


class TestStatsAPISplitsAdapter:
    def test_satisfies_protocol(self) -> None:
        adapter = StatsAPISplitsAdapter(client=_mock_client("player_stats_batter.json"))
        assert isinstance(adapter, PlayerSplitsPort)

    def test_parses_splits(self) -> None:
        adapter = StatsAPISplitsAdapter(client=_mock_client("player_stats_batter.json"))
        result = adapter.get_splits(player_id=592450)
        assert result.meta.available is True
        assert isinstance(result.splits, dict)

    def test_never_raises_on_missing_data(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"people": []})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPISplitsAdapter(client=client)
        result = adapter.get_splits(player_id=592450)
        assert isinstance(result, SplitsResult)


class TestStatsAPIBullpenAdapter:
    def test_satisfies_protocol(self) -> None:
        adapter = StatsAPIBullpenAdapter(client=_mock_client("team_roster.json"))
        assert isinstance(adapter, BullpenPort)

    def test_identifies_relievers_from_roster(self) -> None:
        adapter = StatsAPIBullpenAdapter(client=_mock_client("team_roster.json"))
        result = adapter.get_bullpen_state(team_id=147, date="2026-06-15")
        assert result.meta.available is True
        assert len(result.arms) > 0
        pitcher_names = [arm["fullName"] for arm in result.arms]
        assert "Aaron Judge" not in pitcher_names

    def test_never_raises(self) -> None:
        adapter = StatsAPIBullpenAdapter(
            client=_error_client(500),
            config=StatsAPIConfig(max_retries=0),
        )
        result = adapter.get_bullpen_state(team_id=147, date="2026-06-15")
        assert isinstance(result, BullpenResult)
        assert result.meta.available is False


class TestStatsAPIWeatherAdapter:
    def test_satisfies_protocol(self) -> None:
        adapter = StatsAPIWeatherAdapter(client=_mock_client("game_feed_live.json"))
        assert isinstance(adapter, MLBWeatherPort)

    def test_parses_weather_from_game_feed(self) -> None:
        adapter = StatsAPIWeatherAdapter(client=_mock_client("game_feed_live.json"))
        result = adapter.get_weather(game_pk=717465, game_time_utc="2026-06-15T23:05:00Z")
        assert result.meta.available is True
        assert result.temp_f == 78
        assert result.wind_mph == 12
        assert result.dome is False

    def test_dome_detection(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            data = _load_fixture("game_feed_live.json")
            data["gameData"]["venue"]["fieldInfo"]["roofType"] = "Retractable"
            data["gameData"]["weather"] = {}
            return httpx.Response(200, json=data)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIWeatherAdapter(client=client)
        result = adapter.get_weather(game_pk=717465, game_time_utc="2026-06-15T23:05:00Z")
        assert result.dome is True

    def test_never_raises(self) -> None:
        adapter = StatsAPIWeatherAdapter(
            client=_timeout_client(),
            config=StatsAPIConfig(max_retries=0),
        )
        result = adapter.get_weather(game_pk=717465, game_time_utc="2026-06-15T23:05:00Z")
        assert isinstance(result, MLBWeatherResult)
        assert result.meta.available is False

    def test_url_uses_game_pk(self) -> None:
        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests_made.append(request)
            data = _load_fixture("game_feed_live.json")
            return httpx.Response(200, json=data)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIWeatherAdapter(client=client)
        adapter.get_weather(game_pk=823948, game_time_utc="2026-06-15T23:05:00Z")

        assert len(requests_made) == 1
        assert "/game/823948/feed/live" in str(requests_made[0].url)


class TestStatsAPIBallparkAdapter:
    def test_satisfies_protocol(self) -> None:
        adapter = StatsAPIBallparkAdapter(client=_mock_client("venue.json"))
        assert isinstance(adapter, BallparkPort)

    def test_parses_venue_info(self) -> None:
        adapter = StatsAPIBallparkAdapter(client=_mock_client("venue.json"))
        result = adapter.get_ballpark(venue_id=3313)
        assert result.meta.available is True
        assert result.venue_name == "Yankee Stadium"
        assert result.park_factor >= 0.8

    def test_never_raises_on_unknown_venue(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"message": "Not Found"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIBallparkAdapter(
            client=client,
            config=StatsAPIConfig(max_retries=0),
        )
        result = adapter.get_ballpark(venue_id=99999)
        assert isinstance(result, BallparkResult)
        assert result.meta.available is False


class TestRetryBehavior:
    def test_retries_on_429(self) -> None:
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 3:
                return httpx.Response(429, json={"message": "rate limited"})
            return httpx.Response(200, json=_load_fixture("schedule.json"))

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIScheduleAdapter(
            client=client,
            config=StatsAPIConfig(max_retries=2, backoff_base_seconds=0.01),
        )
        result = adapter.get_schedule(date="2026-06-15")
        assert result.meta.available is True
        assert call_count["n"] == 3

    def test_retries_on_500(self) -> None:
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] < 2:
                return httpx.Response(500, json={"message": "server error"})
            return httpx.Response(200, json=_load_fixture("schedule.json"))

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIScheduleAdapter(
            client=client,
            config=StatsAPIConfig(max_retries=2, backoff_base_seconds=0.01),
        )
        result = adapter.get_schedule(date="2026-06-15")
        assert result.meta.available is True

    def test_gives_up_after_max_retries(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"message": "server error"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIScheduleAdapter(
            client=client,
            config=StatsAPIConfig(max_retries=2, backoff_base_seconds=0.01),
        )
        result = adapter.get_schedule(date="2026-06-15")
        assert result.meta.available is False

    def test_no_retry_on_404(self) -> None:
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(404, json={"message": "Not Found"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        adapter = StatsAPIScheduleAdapter(
            client=client,
            config=StatsAPIConfig(max_retries=2, backoff_base_seconds=0.01),
        )
        result = adapter.get_schedule(date="2026-06-15")
        assert result.meta.available is False
        assert call_count["n"] == 1
