"""Fixture lookup provider backed by API-Football endpoints."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_DEFAULT_BASE_URL = "https://v3.football.api-sports.io"
_DEFAULT_HOST = "v3.football.api-sports.io"


class ApiFootballFixtureProvider:
    """Resolve fixtures through API-Football and map into the pipeline fixture schema."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        host: str = _DEFAULT_HOST,
        timeout_seconds: int = 8,
        urlopen_fn: Callable[..., Any] = urlopen,
    ) -> None:
        self.api_key = api_key or os.getenv("API_FOOTBALL_API_KEY")
        self.base_url = base_url
        self.host = host
        self.timeout_seconds = timeout_seconds
        self.urlopen_fn = urlopen_fn

    def lookup_fixture(self, request: Any) -> dict[str, Any] | None:
        if not self.api_key:
            return None

        try:
            match_date = getattr(request, "parsed_match_date", None) or request.match_date
            home_name = getattr(request, "parsed_home_team", None) or request.home_team
            away_name = getattr(request, "parsed_away_team", None) or request.away_team

            home_team = self._lookup_team(home_name)
            away_team = self._lookup_team(away_name)
            if not home_team or not away_team:
                return None

            fixture_payload = self._fetch_json(
                "/fixtures",
                {
                    "date": match_date,
                    "team": home_team["id"],
                    "opponent": away_team["id"],
                },
            )

            fixture_row = self._choose_fixture(fixture_payload.get("response") or [], home_team["id"], away_team["id"])
            if not fixture_row:
                return None

            return self._map_fixture(fixture_row, home_team, away_team, request)
        except Exception:
            return None

    def _lookup_team(self, team_name: str) -> dict[str, Any] | None:
        payload = self._fetch_json("/teams", {"search": team_name})
        for row in payload.get("response") or []:
            team = row.get("team") or {}
            if str(team.get("name", "")).lower() == team_name.lower():
                return {"id": team.get("id"), "name": team.get("name", team_name)}
        if payload.get("response"):
            first_team = (payload["response"][0] or {}).get("team") or {}
            return {"id": first_team.get("id"), "name": first_team.get("name", team_name)}
        return None

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
    def _choose_fixture(fixtures: list[dict[str, Any]], home_team_id: Any, away_team_id: Any) -> dict[str, Any] | None:
        for row in fixtures:
            teams = row.get("teams") or {}
            home_id = (teams.get("home") or {}).get("id")
            away_id = (teams.get("away") or {}).get("id")
            if str(home_id) == str(home_team_id) and str(away_id) == str(away_team_id):
                return row
        return fixtures[0] if fixtures else None

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

        competition_name = league.get("name") or request.competition
        competition_type = str(league.get("type") or "league").lower()

        return {
            "match_id": str(fixture.get("id")),
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
