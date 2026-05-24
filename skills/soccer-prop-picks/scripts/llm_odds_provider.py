"""LLM-powered odds provider using search grounding for real sportsbook data."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from llm.client import LLMClient


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class LLMOddsProvider:
    """Odds provider that uses an LLM with search grounding to fetch real pre-match odds."""

    def __init__(self, *, client: LLMClient) -> None:
        self._client = client
        self.last_sources: list = []

    def get_odds_snapshots(self, fixture: dict[str, Any]) -> dict[str, Any] | None:
        debug = os.getenv("COLMILLO_ODDS_LLM_DEBUG", "").strip() not in ("", "0", "false")
        try:
            result = self._client.generate_structured(
                system_prompt=self._build_system_prompt(),
                user_prompt=self._build_user_prompt(fixture),
                schema={},
            )
            self.last_sources = list(getattr(self._client, "last_sources", []))
            if debug:
                print(f"[odds-llm-debug] response: {json.dumps(result, default=str)[:2000]}", file=sys.stderr)
            return self._map_response(result)
        except Exception as exc:
            print(f"[odds-provider] WARNING: Odds provider failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            if debug:
                print(f"[odds-llm-debug] error: {type(exc).__name__}: {exc}", file=sys.stderr)
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

        return (
            f"Find pre-match betting odds for {home_name} vs {away_name} "
            f"({competition}, {match_date}) from major sportsbooks.\n\n"
            "Return a JSON object with this exact shape:\n"
            '{"sportsbook_snapshots": [{"source": "sportsbook name", "odds_decimal": 1.85}]}\n\n'
            "Rules:\n"
            "- Include odds from at least 5 sportsbooks (bet365, DraftKings, FanDuel, BetMGM, Pinnacle, etc.)\n"
            "- Use decimal format (European odds), not American or fractional\n"
            "- Return the home team win (1X2 market, home win) odds from each sportsbook\n"
            "- Use real current pre-match odds\n"
            "- If odds are not yet available, return: {\"sportsbook_snapshots\": []}\n"
            "- Return JSON only, no explanation"
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
