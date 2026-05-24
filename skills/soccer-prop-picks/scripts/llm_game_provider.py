"""Basketball game context provider backed by an OpenAI-compatible LLM endpoint.

Fetches NBA game-level data (pace, defensive ratings, odds, rest days, venue)
from a search-grounded LLM and maps into the basketball pipeline schema.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.request import urlopen

from provider_config import LLMFixtureProviderConfig

from llm_fixture_provider import OpenAICompatibleChatClient


class LLMGameProviderError(RuntimeError):
    """Sanitized basketball game LLM provider failure safe to show in CLI output."""


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _truncate_debug(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[:max_chars]}... <truncated {len(value) - max_chars} chars>"


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _should_accept_game(result: dict[str, Any]) -> bool:
    if bool(result.get("game_found")):
        return True
    confidence = str(result.get("confidence") or "").strip().lower()
    return confidence == "high"


def _neutral_fallback(home_team: str, away_team: str) -> dict[str, Any]:
    return {
        "home_team": home_team,
        "away_team": away_team,
        "tipoff_utc": None,
        "home_pace": None,
        "away_pace": None,
        "projected_game_pace": None,
        "home_defensive_rating": None,
        "away_defensive_rating": None,
        "home_win_prob": None,
        "away_win_prob": None,
        "over_under_total": None,
        "spread": None,
        "home_rest_days": None,
        "away_rest_days": None,
        "venue": None,
        "is_playoff": False,
    }


class LLMGameProvider:
    """Resolve NBA game context through an LLM with search grounding."""

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
        self.debug_enabled = _env_flag("COLMILLO_GAME_LLM_DEBUG", default=False)
        self.debug_max_chars = int(os.getenv("COLMILLO_GAME_LLM_DEBUG_MAX_CHARS", "2500"))
        self.last_sources: list = []
        self.client = client or OpenAICompatibleChatClient(
            api_key=resolved.api_key or "",
            base_url=resolved.base_url or "",
            model=resolved.model or "",
            timeout_seconds=timeout_seconds,
            urlopen_fn=urlopen_fn,
        )

    def _debug(self, event: str, payload: dict[str, Any]) -> None:
        if not self.debug_enabled:
            return
        rendered = json.dumps(payload, ensure_ascii=True, default=str)
        clipped = _truncate_debug(rendered, max_chars=max(256, self.debug_max_chars))
        print(f"[game-llm-debug] {event}: {clipped}", file=sys.stderr)

    def lookup_game(
        self,
        *,
        home_team: str,
        away_team: str,
        match_date: str,
    ) -> dict[str, Any] | None:
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            home_team=home_team, away_team=away_team, match_date=match_date,
        )
        self._debug(
            "request",
            {
                "provider": self.config.provider,
                "model": self.config.model,
                "home_team": home_team,
                "away_team": away_team,
                "match_date": match_date,
            },
        )

        try:
            result = self.client.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema={},
            )
        except (LLMGameProviderError, Exception):
            return _neutral_fallback(home_team, away_team)

        self.last_sources = list(getattr(self.client, "last_sources", []))
        self._debug("response", {"provider": self.config.provider, "response": result})

        if not _should_accept_game(result):
            self._debug(
                "game_not_found",
                {
                    "provider": self.config.provider,
                    "reason": result.get("reason", "not provided"),
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                },
            )
            return None

        return self._map_game(result, home_team=home_team, away_team=away_team)

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You resolve NBA basketball game context for a betting-analysis pipeline. "
            "Use current or live game information when your provider has access to it. "
            "Return exactly one JSON object with pace, defensive ratings, odds, rest days, "
            "and venue data. Do not include markdown or prose. "
            "If the teams or date are clearly implausible, set game_found to false. "
            "Never invent game data — but if the matchup is plausible, return your best "
            "assessment with appropriate confidence."
        )

    @staticmethod
    def _build_user_prompt(
        *, home_team: str, away_team: str, match_date: str,
    ) -> str:
        return json.dumps(
            {
                "task": "Resolve this NBA game context as JSON.",
                "today_utc": _utc_now_z(),
                "request": {
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                    "league": "NBA",
                },
                "required_json_shape": {
                    "game_found": True,
                    "confidence": "high|medium|low",
                    "home_team": "official home team name",
                    "away_team": "official away team name",
                    "tipoff_utc": "ISO-8601 UTC timestamp ending with Z, or null",
                    "home_pace": "possessions per 48 minutes (float)",
                    "away_pace": "possessions per 48 minutes (float)",
                    "projected_game_pace": "expected game pace combining both teams (float)",
                    "home_defensive_rating": "points allowed per 100 possessions (float)",
                    "away_defensive_rating": "points allowed per 100 possessions (float)",
                    "home_win_prob": "moneyline-implied win probability 0-1 (float)",
                    "away_win_prob": "moneyline-implied win probability 0-1 (float)",
                    "over_under_total": "Vegas total points line (float)",
                    "spread": "point spread from home perspective, negative = home favored (float)",
                    "home_rest_days": "days since home team last played (integer)",
                    "away_rest_days": "days since away team last played (integer)",
                    "venue": "arena name (string)",
                    "is_playoff": "true if playoff game, false for regular season",
                },
                "rules": [
                    "Return game_found false only if the teams or date are clearly implausible.",
                    "Use the most recent team pace and defensive rating stats available.",
                    "Derive win probabilities from current moneyline odds if available.",
                    "Spread should be negative if home team is favored.",
                    "Rest days of 0 means back-to-back (played yesterday).",
                    "Use null for any field you cannot determine with reasonable confidence.",
                    "Return JSON only — no markdown, no prose.",
                ],
            },
            sort_keys=True,
        )

    @staticmethod
    def _map_game(
        result: dict[str, Any],
        *,
        home_team: str,
        away_team: str,
    ) -> dict[str, Any]:
        def _float_or_none(key: str) -> float | None:
            val = result.get(key)
            if val is None:
                return None
            try:
                return float(val)
            except (TypeError, ValueError):
                return None

        def _int_or_none(key: str) -> int | None:
            val = result.get(key)
            if val is None:
                return None
            try:
                return int(val)
            except (TypeError, ValueError):
                return None

        return {
            "home_team": str(result.get("home_team") or home_team),
            "away_team": str(result.get("away_team") or away_team),
            "tipoff_utc": result.get("tipoff_utc"),
            "home_pace": _float_or_none("home_pace"),
            "away_pace": _float_or_none("away_pace"),
            "projected_game_pace": _float_or_none("projected_game_pace"),
            "home_defensive_rating": _float_or_none("home_defensive_rating"),
            "away_defensive_rating": _float_or_none("away_defensive_rating"),
            "home_win_prob": _float_or_none("home_win_prob"),
            "away_win_prob": _float_or_none("away_win_prob"),
            "over_under_total": _float_or_none("over_under_total"),
            "spread": _float_or_none("spread"),
            "home_rest_days": _int_or_none("home_rest_days"),
            "away_rest_days": _int_or_none("away_rest_days"),
            "venue": result.get("venue"),
            "is_playoff": bool(result.get("is_playoff", False)),
        }
