"""LLM-powered odds provider using search grounding for real sportsbook data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from llm.client import LLMClient


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class LLMOddsProvider:
    """Odds provider that uses an LLM with search grounding to fetch real pre-match odds."""

    def __init__(self, *, client: LLMClient) -> None:
        self._client = client

    def get_odds_snapshots(self, fixture: dict[str, Any]) -> dict[str, Any] | None:
        try:
            result = self._client.generate_structured(
                system_prompt=self._build_system_prompt(),
                user_prompt=self._build_user_prompt(fixture),
                schema={},
            )
            return self._map_response(result)
        except Exception:
            return None

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You provide pre-match soccer betting odds from major sportsbooks for a betting-analysis pipeline. "
            "Use current or live information when available. "
            "Return exactly one JSON object. Do not include markdown or prose."
        )

    @staticmethod
    def _build_user_prompt(fixture: dict[str, Any]) -> str:
        teams = fixture.get("teams", {})
        home = teams.get("home", {})
        away = teams.get("away", {})
        home_name = home.get("team_name", "Home")
        away_name = away.get("team_name", "Away")
        match_date = fixture.get("kickoff_utc", "")[:10] or "unknown"
        competition = fixture.get("competition", "League")

        return json.dumps(
            {
                "task": "Provide pre-match betting odds for this soccer match from multiple sportsbooks.",
                "match": {
                    "home_team": home_name,
                    "away_team": away_name,
                    "date": match_date,
                    "competition": competition,
                },
                "required_json_shape": {
                    "sportsbook_snapshots": [
                        {
                            "source": "sportsbook name (e.g. bet365, DraftKings, FanDuel, BetMGM, Pinnacle)",
                            "odds_decimal": "decimal odds for home team win (float, e.g. 1.85)",
                        }
                    ],
                },
                "rules": [
                    "Return odds from at least 5 different sportsbooks if available.",
                    "Use decimal format (European odds), not American or fractional.",
                    "Return the home team win (1) odds from each sportsbook.",
                    "Use real current pre-match odds from major sportsbooks.",
                    "If odds are not yet available, return an empty sportsbook_snapshots array.",
                    "Return JSON only.",
                ],
            },
            sort_keys=True,
        )

    def _map_response(self, result: dict[str, Any]) -> dict[str, Any]:
        ts = _utc_now_z()
        raw_snapshots = result.get("sportsbook_snapshots", [])
        if not isinstance(raw_snapshots, list):
            raw_snapshots = []

        snapshots: list[dict[str, Any]] = []
        for snap in raw_snapshots:
            if not isinstance(snap, dict):
                continue
            source = str(snap.get("source", "unknown")).strip()
            odds = self._safe_float(snap.get("odds_decimal"))
            if odds is None or odds <= 1.0:
                continue
            snapshots.append({
                "source": source,
                "odds_decimal": round(odds, 2),
                "captured_at_utc": ts,
            })

        if not snapshots:
            return None

        return {
            "source_timestamp_utc": ts,
            "sportsbook_snapshots": snapshots,
        }

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
