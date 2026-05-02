"""Fixture lookup provider backed by API-Football endpoints."""

from __future__ import annotations

import json
from json import JSONDecodeError
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from provider_config import ApiFootballProviderConfig


class ApiFootballProviderError(RuntimeError):
    """Sanitized API-Football provider failure safe to show in CLI/report output."""


def _clean_query(query: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in query.items() if value not in (None, "")}


def _format_api_errors(errors: Any) -> str:
    if isinstance(errors, dict):
        parts = [f"{key}: {value}" for key, value in errors.items() if value]
        return "; ".join(parts) or "unknown API error"
    if isinstance(errors, list):
        return "; ".join(str(item) for item in errors if item) or "unknown API error"
    return str(errors) if errors else "unknown API error"


class ApiFootballFixtureProvider:
    """Resolve fixtures through API-Football and map into the pipeline fixture schema."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        host: str | None = None,
        config: ApiFootballProviderConfig | None = None,
        timeout_seconds: int = 8,
        urlopen_fn: Callable[..., Any] = urlopen,
    ) -> None:
        resolved = config or ApiFootballProviderConfig.from_env()
        self.api_key = api_key or resolved.api_key
        self.base_url = base_url or resolved.base_url
        self.host = host or resolved.host
        ApiFootballProviderConfig(api_key=self.api_key, base_url=self.base_url, host=self.host).validate()
        self.timeout_seconds = timeout_seconds
        self.urlopen_fn = urlopen_fn

    def lookup_fixture(self, request: Any) -> dict[str, Any] | None:
        match_date = getattr(request, "parsed_match_date", None) or request.match_date
        home_name = getattr(request, "parsed_home_team", None) or request.home_team
        away_name = getattr(request, "parsed_away_team", None) or request.away_team

        league_id = self._resolve_league_id(request)
        season = getattr(request, "season", None)

        home_team = self._lookup_team(home_name, league_id=league_id, season=season)
        away_team = self._lookup_team(away_name, league_id=league_id, season=season)
        if not home_team or not away_team:
            return None

        fixture_payload = self._fetch_json(
            "/fixtures",
            self._fixture_query(
                match_date=match_date,
                home_team_id=home_team["id"],
                league_id=league_id,
                season=season,
            ),
        )

        fixture_row = self._choose_fixture(fixture_payload.get("response") or [], home_team["id"], away_team["id"])
        if not fixture_row:
            return None

        return self._map_fixture(fixture_row, home_team, away_team, request)

    def _resolve_league_id(self, request: Any) -> str | None:
        explicit_league_id = getattr(request, "league_id", None)
        if explicit_league_id:
            return str(explicit_league_id)

        season = getattr(request, "season", None)
        if not season:
            return None

        league_name = self._league_search_name(request)
        if not league_name:
            return None

        query: dict[str, Any] = {"search": league_name}
        query["season"] = season

        payload = self._fetch_json("/leagues", query)
        response = payload.get("response") or []
        for row in response:
            league = row.get("league") or {}
            if str(league.get("name", "")).lower() == league_name.lower():
                league_id = league.get("id")
                return str(league_id) if league_id is not None else None
        if response:
            league = (response[0] or {}).get("league") or {}
            league_id = league.get("id")
            return str(league_id) if league_id is not None else None
        return None

    @staticmethod
    def _league_search_name(request: Any) -> str | None:
        candidates: list[str] = []
        candidates.extend(getattr(request, "competition_hints", None) or [])
        competition = getattr(request, "competition", None)
        if competition:
            candidates.append(str(competition))
        for candidate in candidates:
            value = str(candidate).strip()
            if value and value.lower() != "league":
                return value
        return None

    def _lookup_team(self, team_name: str, *, league_id: str | None, season: str | None) -> dict[str, Any] | None:
        query: dict[str, Any] = {"search": team_name}
        if league_id and season:
            query.update({"league": league_id, "season": season})
        payload = self._fetch_json("/teams", query)
        for row in payload.get("response") or []:
            team = row.get("team") or {}
            if str(team.get("name", "")).lower() == team_name.lower():
                return {"id": team.get("id"), "name": team.get("name", team_name)}
        if payload.get("response"):
            first_team = (payload["response"][0] or {}).get("team") or {}
            return {"id": first_team.get("id"), "name": first_team.get("name", team_name)}
        return None

    @staticmethod
    def _fixture_query(
        *,
        match_date: str,
        home_team_id: Any,
        league_id: str | None,
        season: str | None,
    ) -> dict[str, Any]:
        if league_id and season:
            return {"date": match_date, "league": league_id, "season": season}
        return {"date": match_date, "team": home_team_id}

    def _fetch_json(self, path: str, query: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}?{urlencode(_clean_query(query))}"
        request = Request(
            url,
            headers={
                "x-apisports-key": self.api_key or "",
                "x-rapidapi-host": self.host,
            },
        )
        try:
            with self.urlopen_fn(request, timeout=self.timeout_seconds) as response:
                status_code = getattr(response, "status", None) or getattr(response, "code", None)
                if status_code is not None and int(status_code) >= 400:
                    raise ApiFootballProviderError(f"API-Football request failed for {path}: HTTP {status_code}")
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ApiFootballProviderError(f"API-Football request failed for {path}: HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ApiFootballProviderError(f"API-Football request failed for {path}: {exc.__class__.__name__}") from exc
        except JSONDecodeError as exc:
            raise ApiFootballProviderError(f"API-Football returned invalid JSON for {path}") from exc

        if not isinstance(payload, dict):
            raise ApiFootballProviderError(f"API-Football returned an invalid payload for {path}")
        errors = payload.get("errors")
        if errors:
            raise ApiFootballProviderError(f"API-Football returned errors for {path}: {_format_api_errors(errors)}")
        return payload

    @staticmethod
    def _choose_fixture(fixtures: list[dict[str, Any]], home_team_id: Any, away_team_id: Any) -> dict[str, Any] | None:
        for row in fixtures:
            teams = row.get("teams") or {}
            home_id = (teams.get("home") or {}).get("id")
            away_id = (teams.get("away") or {}).get("id")
            if str(home_id) == str(home_team_id) and str(away_id) == str(away_team_id):
                return row
        for row in fixtures:
            teams = row.get("teams") or {}
            home_id = (teams.get("home") or {}).get("id")
            away_id = (teams.get("away") or {}).get("id")
            if str(home_id) == str(away_team_id) and str(away_id) == str(home_team_id):
                return row
        if len(fixtures) == 1:
            teams = fixtures[0].get("teams") or {}
            home_id = (teams.get("home") or {}).get("id")
            away_id = (teams.get("away") or {}).get("id")
            if home_id is None and away_id is None:
                return fixtures[0]
        return None

    @staticmethod
    def _as_utc_z(raw_datetime: str | None) -> str | None:
        if not raw_datetime:
            return None
        dt = datetime.fromisoformat(raw_datetime.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _map_fixture(self, fixture_row: dict[str, Any], home_team: dict[str, Any], away_team: dict[str, Any], request: Any) -> dict[str, Any]:
        fixture = fixture_row.get("fixture") or {}
        league = fixture_row.get("league") or {}
        teams = fixture_row.get("teams") or {}
        api_home = teams.get("home") or {}
        api_away = teams.get("away") or {}
        venue = fixture.get("venue") or {}
        status = fixture.get("status") or {}

        competition_name = league.get("name") or request.competition
        competition_type = str(league.get("type") or "league").lower()

        mapped = {
            "match_id": str(fixture.get("id") or "unknown"),
            "competition": competition_name,
            "competition_type": competition_type,
            "is_elimination": competition_type == "cup",
            "overtime_possible": competition_type == "cup",
            "kickoff_utc": self._as_utc_z(fixture.get("date")),
            "venue": {
                "name": venue.get("name") or "Unknown Venue",
                "city": venue.get("city") or "Unknown",
                "country": league.get("country") or "Unknown",
            },
            "teams": {
                "home": {
                    "team_id": str(api_home.get("id") or home_team.get("id")),
                    "team_name": api_home.get("name") or home_team.get("name"),
                },
                "away": {
                    "team_id": str(api_away.get("id") or away_team.get("id")),
                    "team_name": api_away.get("name") or away_team.get("name"),
                },
            },
        }
        mapped_status: dict[str, Any] = {}
        if status.get("long"):
            mapped_status["long"] = str(status["long"])
        if status.get("short"):
            mapped_status["short"] = str(status["short"])
        if status.get("elapsed") is not None:
            mapped_status["elapsed"] = int(status["elapsed"])
        if mapped_status:
            mapped["status"] = mapped_status
        return mapped


class ApiFootballOddsSnapshotProvider:
    """Fetch fixture odds snapshots through API-Football and normalize bookmaker snapshots."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        host: str | None = None,
        config: ApiFootballProviderConfig | None = None,
        timeout_seconds: int = 8,
        urlopen_fn: Callable[..., Any] = urlopen,
    ) -> None:
        resolved = config or ApiFootballProviderConfig.from_env()
        self.api_key = api_key or resolved.api_key
        self.base_url = base_url or resolved.base_url
        self.host = host or resolved.host
        ApiFootballProviderConfig(api_key=self.api_key, base_url=self.base_url, host=self.host).validate()
        self.timeout_seconds = timeout_seconds
        self.urlopen_fn = urlopen_fn

    def get_odds_snapshots(self, fixture: dict[str, Any]) -> dict[str, Any] | None:
        fixture_id = fixture.get("match_id")
        if not fixture_id:
            return {"source_timestamp_utc": self._utc_now_z(), "sportsbook_snapshots": []}

        try:
            payload = self._fetch_json("/odds", {"fixture": fixture_id})
        except Exception:
            return None

        source_ts = self._utc_now_z()
        snapshots: list[dict[str, Any]] = []
        for market_row in payload.get("response") or []:
            update_ts = self._as_utc_z((market_row.get("update") or {}).get("date")) or source_ts
            for bookmaker in market_row.get("bookmakers") or []:
                odds_decimal = self._extract_decimal_odd(bookmaker.get("bets") or [])
                if odds_decimal is None:
                    continue
                snapshots.append(
                    {
                        "source": bookmaker.get("name") or "unknown_book",
                        "odds_decimal": odds_decimal,
                        "captured_at_utc": update_ts,
                    }
                )

        return {"source_timestamp_utc": source_ts, "sportsbook_snapshots": snapshots}

    def _fetch_json(self, path: str, query: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}?{urlencode(query)}"
        request = Request(
            url,
            headers={
                "x-apisports-key": self.api_key or "",
                "x-rapidapi-host": self.host,
            },
        )
        with self.urlopen_fn(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _extract_decimal_odd(bets: list[dict[str, Any]]) -> float | None:
        for bet in bets:
            for value in bet.get("values") or []:
                label = str(value.get("value") or "").lower()
                odd = value.get("odd")
                if "over" not in label:
                    continue
                try:
                    return float(odd)
                except (TypeError, ValueError):
                    continue

        for bet in bets:
            for value in bet.get("values") or []:
                try:
                    return float(value.get("odd"))
                except (TypeError, ValueError):
                    continue
        return None

    @staticmethod
    def _as_utc_z(raw_datetime: str | None) -> str | None:
        if not raw_datetime:
            return None
        dt = datetime.fromisoformat(raw_datetime.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _utc_now_z() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
