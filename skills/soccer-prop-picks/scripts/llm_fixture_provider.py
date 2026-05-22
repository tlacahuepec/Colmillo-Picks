"""Fixture lookup provider backed by an OpenAI-compatible LLM endpoint."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from json import JSONDecodeError
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from provider_config import LLMFixtureProviderConfig


class LLMFixtureProviderError(RuntimeError):
    """Sanitized fixture LLM provider failure safe to show in CLI output."""


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _team_id(team_name: str) -> str:
    alpha = "".join(ch for ch in team_name.upper() if ch.isalpha())
    if len(alpha) >= 3:
        return alpha[:3]
    return (alpha + "XXX")[:3]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "unknown"


def _as_utc_z(raw_datetime: str | None) -> str | None:
    if not raw_datetime:
        return None
    try:
        dt = datetime.fromisoformat(str(raw_datetime).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_string(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    cleaned = str(value).strip()
    return cleaned or fallback


def _extract_message_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMFixtureProviderError("Fixture LLM returned no choices")
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        if parts:
            return "\n".join(parts)
    raise LLMFixtureProviderError("Fixture LLM returned empty content")


def _parse_json_object(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise LLMFixtureProviderError("Fixture LLM did not return JSON") from None
        try:
            parsed = json.loads(match.group(0))
        except JSONDecodeError as exc:
            raise LLMFixtureProviderError("Fixture LLM returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMFixtureProviderError("Fixture LLM returned non-object JSON")
    return parsed


class OpenAICompatibleChatClient:
    """Small standard-library client for chat-completions-compatible APIs."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 20,
        urlopen_fn: Callable[..., Any] = urlopen,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.urlopen_fn = urlopen_fn

    def generate_json(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.urlopen_fn(request, timeout=self.timeout_seconds) as response:
                status_code = getattr(response, "status", None) or getattr(response, "code", None)
                if status_code is not None and int(status_code) >= 400:
                    raise LLMFixtureProviderError(f"Fixture LLM request failed: HTTP {status_code}")
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise LLMFixtureProviderError(f"Fixture LLM request failed: HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise LLMFixtureProviderError(f"Fixture LLM request failed: {exc.__class__.__name__}") from exc
        except JSONDecodeError as exc:
            raise LLMFixtureProviderError("Fixture LLM returned invalid response JSON") from exc

        if not isinstance(payload, dict):
            raise LLMFixtureProviderError("Fixture LLM returned invalid response payload")
        return _parse_json_object(_extract_message_content(payload))

    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        return self.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)


class LLMFixtureProvider:
    """Resolve fixtures through an LLM and map into the pipeline fixture schema."""

    provider_label = "LLM"

    def __init__(
        self,
        *,
        config: LLMFixtureProviderConfig | None = None,
        client: Any | None = None,
        timeout_seconds: int = 20,
        urlopen_fn: Callable[..., Any] = urlopen,
    ) -> None:
        resolved = config or LLMFixtureProviderConfig.from_env()
        resolved.validate()
        self.config = resolved
        self.client = client or OpenAICompatibleChatClient(
            api_key=resolved.api_key or "",
            base_url=resolved.base_url or "",
            model=resolved.model or "",
            timeout_seconds=timeout_seconds,
            urlopen_fn=urlopen_fn,
        )

    def lookup_fixture(self, request: Any) -> dict[str, Any] | None:
        result = self.client.generate_structured(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(request),
            schema={},
        )
        if not bool(result.get("match_found")):
            return None
        return self._map_fixture(result, request)

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You resolve soccer fixture metadata for a betting-analysis pipeline. "
            "Use current or live match information when your provider has access to it. "
            "Return exactly one JSON object. Do not include markdown or prose. "
            "If the exact requested fixture cannot be verified, set match_found to false. "
            "Never invent a fixture."
        )

    @staticmethod
    def _build_user_prompt(request: Any) -> str:
        match_date = getattr(request, "parsed_match_date", None) or request.match_date
        home_team = getattr(request, "parsed_home_team", None) or request.home_team
        away_team = getattr(request, "parsed_away_team", None) or request.away_team
        competition = getattr(request, "competition", None) or "League"
        competition_hints = getattr(request, "competition_hints", None) or []

        return json.dumps(
            {
                "task": "Resolve this soccer match as JSON.",
                "today_utc": _utc_now_z(),
                "request": {
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                    "competition": competition,
                    "competition_hints": competition_hints,
                },
                "required_json_shape": {
                    "match_found": True,
                    "confidence": "high|medium|low",
                    "match_id": "provider fixture id or stable generated id",
                    "competition": "competition name",
                    "competition_type": "league|cup",
                    "is_elimination": False,
                    "overtime_possible": False,
                    "kickoff_utc": "ISO-8601 UTC timestamp ending with Z, or null if unknown",
                    "venue": {"name": "stadium", "city": "city", "country": "country"},
                    "teams": {
                        "home": {"team_id": "stable id/code", "team_name": "official home team"},
                        "away": {"team_id": "stable id/code", "team_name": "official away team"},
                    },
                    "status": {"long": "Not Started", "short": "NS"},
                    "sources": [{"title": "source title", "url": "https://..."}],
                },
                "rules": [
                    "Return match_found false if the teams, competition, or date do not match.",
                    "Prefer official home/away orientation over the order in the request.",
                    "Use null for unknown optional values instead of guessing.",
                    "Return JSON only.",
                ],
            },
            sort_keys=True,
        )

    def _map_fixture(self, result: dict[str, Any], request: Any) -> dict[str, Any]:
        match_date = getattr(request, "parsed_match_date", None) or request.match_date
        requested_home = getattr(request, "parsed_home_team", None) or request.home_team
        requested_away = getattr(request, "parsed_away_team", None) or request.away_team
        requested_competition = getattr(request, "competition", None) or "League"

        teams = result.get("teams") if isinstance(result.get("teams"), dict) else {}
        home = teams.get("home") if isinstance(teams.get("home"), dict) else {}
        away = teams.get("away") if isinstance(teams.get("away"), dict) else {}
        home_name = _clean_string(home.get("team_name"), requested_home)
        away_name = _clean_string(away.get("team_name"), requested_away)

        competition = _clean_string(result.get("competition"), requested_competition)
        competition_type = _clean_string(result.get("competition_type"), "league").lower()
        venue = result.get("venue") if isinstance(result.get("venue"), dict) else {}
        match_id = _clean_string(
            result.get("match_id"),
            f"llm-{_slug(competition)}-{_slug(home_name)}-{_slug(away_name)}-{match_date}",
        )

        mapped: dict[str, Any] = {
            "match_id": match_id,
            "competition": competition,
            "competition_type": competition_type,
            "is_elimination": bool(result.get("is_elimination", competition_type == "cup")),
            "overtime_possible": bool(result.get("overtime_possible", competition_type == "cup")),
            "kickoff_utc": _as_utc_z(result.get("kickoff_utc")),
            "venue": {
                "name": _clean_string(venue.get("name"), "Unknown Venue"),
                "city": _clean_string(venue.get("city"), "Unknown"),
                "country": _clean_string(venue.get("country"), "Unknown"),
            },
            "teams": {
                "home": {
                    "team_id": _clean_string(home.get("team_id"), _team_id(home_name)),
                    "team_name": home_name,
                },
                "away": {
                    "team_id": _clean_string(away.get("team_id"), _team_id(away_name)),
                    "team_name": away_name,
                },
            },
        }

        status = result.get("status")
        if isinstance(status, dict):
            mapped_status: dict[str, Any] = {}
            if status.get("long"):
                mapped_status["long"] = str(status["long"])
            if status.get("short"):
                mapped_status["short"] = str(status["short"])
            if status.get("elapsed") is not None:
                try:
                    mapped_status["elapsed"] = int(status["elapsed"])
                except (TypeError, ValueError):
                    pass
            if mapped_status:
                mapped["status"] = mapped_status

        return mapped
