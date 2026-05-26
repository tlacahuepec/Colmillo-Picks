"""MLB-StatsAPI adapter implementations for all provider ports."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

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

_BASE_URL = "https://statsapi.mlb.com"

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

_PARK_FACTORS: dict[int, tuple[float, float | None]] = {
    3313: (1.05, 1.15),   # Yankee Stadium
    15: (0.96, 0.85),     # Chase Field (roof)
    4: (0.98, 0.90),      # Tropicana Field (dome)
    680: (1.02, 1.05),    # Coors Field
    2394: (1.00, 1.00),   # Globe Life Field
    17: (0.95, 0.82),     # Oracle Park
    31: (1.03, 1.08),     # Great American Ball Park
    2889: (0.97, 0.92),   # Dodger Stadium
}


@dataclass
class StatsAPIConfig:
    base_url: str = _BASE_URL
    timeout_seconds: float = 10.0
    max_retries: int = 2
    backoff_base_seconds: float = 1.0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_meta(
    *, available: bool, source: str = "mlb-statsapi", error: str | None = None
) -> MLBProviderMeta:
    status = "fresh" if available else ("error" if error else "unavailable")
    return MLBProviderMeta(
        available=available,
        source=source,
        retrieved_at_utc=_utc_now_iso(),
        error_message=error,
        provider_status=status,
    )


def _fetch_with_retry(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, str] | None = None,
    config: StatsAPIConfig | None = None,
) -> httpx.Response | None:
    cfg = config or StatsAPIConfig()
    attempts = 0
    max_attempts = 1 + cfg.max_retries

    while attempts < max_attempts:
        try:
            response = client.get(url, params=params, timeout=cfg.timeout_seconds)
            if response.status_code < 400:
                return response
            if response.status_code not in _RETRYABLE_STATUS_CODES:
                return response
            attempts += 1
            if attempts < max_attempts:
                time.sleep(cfg.backoff_base_seconds * (2 ** (attempts - 1)))
        except (httpx.HTTPError, OSError):
            attempts += 1
            if attempts < max_attempts:
                time.sleep(cfg.backoff_base_seconds * (2 ** (attempts - 1)))

    return None


class StatsAPIScheduleAdapter:
    def __init__(
        self, *, client: httpx.Client | None = None, config: StatsAPIConfig | None = None
    ) -> None:
        self._client = client or httpx.Client()
        self._config = config or StatsAPIConfig()

    def get_schedule(self, *, date: str, team_id: int | None = None) -> MLBScheduleResult:
        try:
            url = f"{self._config.base_url}/api/v1/schedule"
            params: dict[str, str] = {"sportId": "1", "date": date}
            if team_id is not None:
                params["teamId"] = str(team_id)

            response = _fetch_with_retry(self._client, url, params=params, config=self._config)
            if response is None:
                return MLBScheduleResult(meta=_build_meta(available=False, error="request_failed"))

            if response.status_code >= 400:
                return MLBScheduleResult(
                    meta=_build_meta(available=False, error=f"http_{response.status_code}")
                )

            data = response.json()
            games: list[dict[str, Any]] = []
            for date_entry in data.get("dates", []):
                games.extend(date_entry.get("games", []))

            return MLBScheduleResult(meta=_build_meta(available=True), games=games)
        except Exception as exc:
            return MLBScheduleResult(meta=_build_meta(available=False, error=str(exc)))


class StatsAPIPitcherAdapter:
    def __init__(
        self, *, client: httpx.Client | None = None, config: StatsAPIConfig | None = None
    ) -> None:
        self._client = client or httpx.Client()
        self._config = config or StatsAPIConfig()

    def get_probable_pitchers(self, *, game_pk: int) -> ProbablePitcherResult:
        try:
            url = f"{self._config.base_url}/api/v1/schedule"
            params = {"sportId": "1", "gamePk": str(game_pk), "hydrate": "probablePitcher"}

            response = _fetch_with_retry(self._client, url, params=params, config=self._config)
            if response is None:
                return ProbablePitcherResult(meta=_build_meta(available=False, error="request_failed"))

            if response.status_code >= 400:
                return ProbablePitcherResult(
                    meta=_build_meta(available=False, error=f"http_{response.status_code}")
                )

            data = response.json()
            game = self._find_game(data, game_pk)
            if game is None:
                return ProbablePitcherResult(meta=_build_meta(available=True))

            teams = game.get("teams", {})
            home_pitcher = teams.get("home", {}).get("probablePitcher")
            away_pitcher = teams.get("away", {}).get("probablePitcher")

            return ProbablePitcherResult(
                meta=_build_meta(available=True),
                home_pitcher=home_pitcher,
                away_pitcher=away_pitcher,
            )
        except Exception as exc:
            return ProbablePitcherResult(meta=_build_meta(available=False, error=str(exc)))

    def _find_game(self, data: dict[str, Any], game_pk: int) -> dict[str, Any] | None:
        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                if game.get("gamePk") == game_pk:
                    return game
        return None


class StatsAPILineupsAdapter:
    def __init__(
        self, *, client: httpx.Client | None = None, config: StatsAPIConfig | None = None
    ) -> None:
        self._client = client or httpx.Client()
        self._config = config or StatsAPIConfig()

    def get_lineups(self, *, game_pk: int) -> MLBLineupsResult:
        try:
            url = f"{self._config.base_url}/api/v1.1/game/{game_pk}/feed/live"

            response = _fetch_with_retry(self._client, url, config=self._config)
            if response is None:
                return MLBLineupsResult(meta=_build_meta(available=False, error="request_failed"))

            if response.status_code >= 400:
                return MLBLineupsResult(
                    meta=_build_meta(available=False, error=f"http_{response.status_code}")
                )

            data = response.json()
            boxscore = data.get("liveData", {}).get("boxscore", {}).get("teams", {})
            game_state = data.get("gameData", {}).get("status", {}).get("abstractGameState", "Preview")

            home_order = self._parse_order(boxscore.get("home", {}))
            away_order = self._parse_order(boxscore.get("away", {}))

            confirmed = game_state != "Preview" and len(home_order) > 0 and len(away_order) > 0

            return MLBLineupsResult(
                meta=_build_meta(available=True),
                home_order=home_order,
                away_order=away_order,
                confirmed=confirmed,
            )
        except Exception as exc:
            return MLBLineupsResult(meta=_build_meta(available=False, error=str(exc)))

    def _parse_order(self, team_data: dict[str, Any]) -> list[dict[str, Any]]:
        batting_order = team_data.get("battingOrder", [])
        players = team_data.get("players", {})
        order: list[dict[str, Any]] = []
        for player_id in batting_order:
            player_key = f"ID{player_id}"
            player_info = players.get(player_key, {})
            person = player_info.get("person", {})
            position = player_info.get("position", {})
            order.append({
                "id": person.get("id", player_id),
                "fullName": person.get("fullName", "Unknown"),
                "position": position.get("abbreviation", ""),
                "battingOrder": player_info.get("battingOrder", ""),
            })
        return order


class StatsAPIPlayerStatsAdapter:
    def __init__(
        self, *, client: httpx.Client | None = None, config: StatsAPIConfig | None = None
    ) -> None:
        self._client = client or httpx.Client()
        self._config = config or StatsAPIConfig()

    def get_player_stats(self, *, player_id: int, season: int | None = None) -> MLBPlayerStatsResult:
        try:
            url = f"{self._config.base_url}/api/v1/people/{player_id}"
            params = {"hydrate": "stats(group=[hitting,pitching],type=[season,gameLog])"}

            response = _fetch_with_retry(self._client, url, params=params, config=self._config)
            if response is None:
                return MLBPlayerStatsResult(meta=_build_meta(available=False, error="request_failed"))

            if response.status_code >= 400:
                return MLBPlayerStatsResult(
                    meta=_build_meta(available=False, error=f"http_{response.status_code}")
                )

            data = response.json()
            people = data.get("people", [])
            if not people:
                return MLBPlayerStatsResult(meta=_build_meta(available=False, error="player_not_found"))

            player = people[0]
            season_stats: dict[str, Any] = {}
            game_log: list[dict[str, Any]] = []

            for stat_group in player.get("stats", []):
                stat_type = stat_group.get("type", {}).get("displayName", "")
                splits = stat_group.get("splits", [])
                if stat_type == "season" and splits:
                    season_stats = splits[0].get("stat", {})
                elif stat_type == "gameLog":
                    game_log = [
                        {"date": s.get("date", ""), **s.get("stat", {})} for s in splits
                    ]

            return MLBPlayerStatsResult(
                meta=_build_meta(available=True),
                player_id=player_id,
                season_stats=season_stats,
                game_log=game_log,
            )
        except Exception as exc:
            return MLBPlayerStatsResult(meta=_build_meta(available=False, error=str(exc)))


class StatsAPISplitsAdapter:
    def __init__(
        self, *, client: httpx.Client | None = None, config: StatsAPIConfig | None = None
    ) -> None:
        self._client = client or httpx.Client()
        self._config = config or StatsAPIConfig()

    def get_splits(self, *, player_id: int, season: int | None = None) -> SplitsResult:
        try:
            url = f"{self._config.base_url}/api/v1/people/{player_id}"
            params = {"hydrate": "stats(group=[hitting,pitching],type=[season,gameLog])"}

            response = _fetch_with_retry(self._client, url, params=params, config=self._config)
            if response is None:
                return SplitsResult(meta=_build_meta(available=False, error="request_failed"))

            if response.status_code >= 400:
                return SplitsResult(
                    meta=_build_meta(available=False, error=f"http_{response.status_code}")
                )

            data = response.json()
            people = data.get("people", [])
            if not people:
                return SplitsResult(meta=_build_meta(available=True), splits={})

            player = people[0]
            splits: dict[str, dict[str, float]] = {}

            for stat_group in player.get("stats", []):
                stat_type = stat_group.get("type", {}).get("displayName", "")
                if stat_type == "season":
                    stat_splits = stat_group.get("splits", [])
                    if stat_splits:
                        raw = stat_splits[0].get("stat", {})
                        splits["season"] = {
                            k: float(v) for k, v in raw.items() if _is_numeric(v)
                        }

            return SplitsResult(meta=_build_meta(available=True), splits=splits)
        except Exception as exc:
            return SplitsResult(meta=_build_meta(available=False, error=str(exc)))


class StatsAPIBullpenAdapter:
    def __init__(
        self, *, client: httpx.Client | None = None, config: StatsAPIConfig | None = None
    ) -> None:
        self._client = client or httpx.Client()
        self._config = config or StatsAPIConfig()

    def get_bullpen_state(self, *, team_id: int, date: str) -> BullpenResult:
        try:
            url = f"{self._config.base_url}/api/v1/teams/{team_id}/roster"
            params = {"rosterType": "active"}

            response = _fetch_with_retry(self._client, url, params=params, config=self._config)
            if response is None:
                return BullpenResult(meta=_build_meta(available=False, error="request_failed"))

            if response.status_code >= 400:
                return BullpenResult(
                    meta=_build_meta(available=False, error=f"http_{response.status_code}")
                )

            data = response.json()
            roster = data.get("roster", [])
            arms: list[dict[str, Any]] = []

            for player in roster:
                position = player.get("position", {})
                if position.get("type") != "Pitcher":
                    continue
                person = player.get("person", {})
                arms.append({
                    "id": person.get("id"),
                    "fullName": person.get("fullName", "Unknown"),
                    "available": True,
                })

            return BullpenResult(meta=_build_meta(available=True), arms=arms)
        except Exception as exc:
            return BullpenResult(meta=_build_meta(available=False, error=str(exc)))


class StatsAPIWeatherAdapter:
    def __init__(
        self, *, client: httpx.Client | None = None, config: StatsAPIConfig | None = None
    ) -> None:
        self._client = client or httpx.Client()
        self._config = config or StatsAPIConfig()

    def get_weather(self, *, game_pk: int, game_time_utc: str) -> MLBWeatherResult:
        try:
            url = f"{self._config.base_url}/api/v1.1/game/{game_pk}/feed/live"

            response = _fetch_with_retry(self._client, url, config=self._config)
            if response is None:
                return MLBWeatherResult(meta=_build_meta(available=False, error="request_failed"))

            if response.status_code >= 400:
                return MLBWeatherResult(
                    meta=_build_meta(available=False, error=f"http_{response.status_code}")
                )

            data = response.json()
            game_data = data.get("gameData", {})
            weather = game_data.get("weather", {})
            venue_info = game_data.get("venue", {}).get("fieldInfo", {})

            roof_type = venue_info.get("roofType", "Open")
            dome = roof_type.lower() in ("dome", "retractable", "closed")

            temp_f = _parse_int(weather.get("temp"))
            wind_str = weather.get("wind", "")
            wind_mph = _parse_wind_mph(wind_str)
            wind_direction = _parse_wind_direction(wind_str)

            return MLBWeatherResult(
                meta=_build_meta(available=True),
                temp_f=temp_f,
                wind_mph=wind_mph,
                wind_direction=wind_direction,
                dome=dome,
            )
        except Exception as exc:
            return MLBWeatherResult(meta=_build_meta(available=False, error=str(exc)))


class StatsAPIBallparkAdapter:
    def __init__(
        self, *, client: httpx.Client | None = None, config: StatsAPIConfig | None = None
    ) -> None:
        self._client = client or httpx.Client()
        self._config = config or StatsAPIConfig()

    def get_ballpark(self, *, venue_id: int) -> BallparkResult:
        try:
            url = f"{self._config.base_url}/api/v1/venues/{venue_id}"

            response = _fetch_with_retry(self._client, url, config=self._config)
            if response is None:
                return BallparkResult(meta=_build_meta(available=False, error="request_failed"))

            if response.status_code >= 400:
                return BallparkResult(
                    meta=_build_meta(available=False, error=f"http_{response.status_code}")
                )

            data = response.json()
            venues = data.get("venues", [])
            if not venues:
                return BallparkResult(meta=_build_meta(available=False, error="venue_not_found"))

            venue = venues[0]
            venue_name = venue.get("name", "")
            park_factor, hr_factor = _PARK_FACTORS.get(venue_id, (1.0, None))

            return BallparkResult(
                meta=_build_meta(available=True),
                park_factor=park_factor,
                hr_factor=hr_factor,
                venue_name=venue_name,
            )
        except Exception as exc:
            return BallparkResult(meta=_build_meta(available=False, error=str(exc)))


def _is_numeric(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value.lstrip("."))
            return True
        except (ValueError, AttributeError):
            return False
    return False


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _parse_wind_mph(wind_str: str) -> int | None:
    match = re.search(r"(\d+)\s*mph", wind_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _parse_wind_direction(wind_str: str) -> str | None:
    parts = wind_str.split(",")
    if len(parts) >= 2:
        return parts[1].strip()
    return None
