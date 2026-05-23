"""LLM-powered lineup provider using search grounding for real player data."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from llm.client import LLMClient


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _team_id(team_name: str) -> str:
    alpha = [ch for ch in team_name.upper() if ch.isalpha()]
    return "".join(alpha[:3]) if len(alpha) >= 3 else "UNK"


class LLMLineupProvider:
    """Lineup provider that uses an LLM with search grounding to fetch real data."""

    def __init__(self, *, client: LLMClient) -> None:
        self._client = client
        self.last_sources: list = []

    def get_lineups_and_availability(self, fixture: dict[str, Any]) -> dict[str, Any] | None:
        debug = os.getenv("COLMILLO_LINEUP_LLM_DEBUG", "").strip() not in ("", "0", "false")
        try:
            result = self._client.generate_structured(
                system_prompt=self._build_system_prompt(),
                user_prompt=self._build_user_prompt(fixture),
                schema={},
            )
            self.last_sources = list(getattr(self._client, "last_sources", []))
            if debug:
                print(f"[lineup-llm-debug] response: {json.dumps(result, default=str)[:2000]}", file=sys.stderr)
            return self._map_response(result, fixture)
        except Exception as exc:
            print(f"[lineup-provider] WARNING: Lineup provider failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            if debug:
                print(f"[lineup-llm-debug] error: {type(exc).__name__}: {exc}", file=sys.stderr)
            return None

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You provide projected soccer lineup data for a betting-analysis pipeline. "
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
            f"Provide projected lineups and key player statistics for "
            f"{home_name} vs {away_name} ({competition}, {match_date}).\n\n"
            "Return a JSON object with this exact shape:\n"
            "{\n"
            '  "teams": {\n'
            '    "home": {"formation": "4-2-3-1", "starters": ["11 player full names"], "injuries": ["names"], "suspensions": ["names"]},\n'
            '    "away": {"formation": "4-2-3-1", "starters": ["11 player full names"], "injuries": ["names"], "suspensions": ["names"]}\n'
            "  },\n"
            '  "players": [\n'
            '    {"player_name": "full name", "team": "home|away", "role_tag": "GK|CB|LB|RB|CM|CDM|CAM|LM|RM|ST|CF",\n'
            '     "expected_minutes": 90, "substitution_risk": "low|medium|high", "captain": false,\n'
            '     "is_lone_striker": false, "expected_passes_per_game": 45.2, "expected_shots_per_game": 2.1}\n'
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Include projected starting XI for both teams based on latest available information\n"
            "- List all currently injured and suspended players\n"
            f"- In the players array, include exactly 6 key players: 3 from {home_name} "
            f"(1 midfielder, 1 forward, 1 defender) and 3 from {away_name} (1 midfielder, 1 forward, 1 defender)\n"
            "- For each player, provide their season average passes per game and shots per game\n"
            "- Use real current-season statistics, not estimates\n"
            "- Return JSON only, no explanation"
        )

    def _map_response(self, result: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
        teams_data = result.get("teams", {})
        fixture_teams = fixture.get("teams", {})
        home_team_id = fixture_teams.get("home", {}).get("team_id", "HOM")
        away_team_id = fixture_teams.get("away", {}).get("team_id", "AWY")

        mapped_teams: dict[str, Any] = {}
        for side in ("home", "away"):
            side_data = teams_data.get(side, {})
            starters = side_data.get("starters", [])
            if not isinstance(starters, list):
                starters = []
            mapped_teams[side] = {
                "status": "projected",
                "formation": str(side_data.get("formation", "4-4-2")),
                "starters": [str(s) for s in starters[:11]],
                "injuries": [str(i) for i in (side_data.get("injuries") or [])],
                "suspensions": [str(s) for s in (side_data.get("suspensions") or [])],
            }

        raw_players = result.get("players", [])
        if not isinstance(raw_players, list):
            raw_players = []

        mapped_players: list[dict[str, Any]] = []
        for idx, p in enumerate(raw_players):
            if not isinstance(p, dict):
                continue
            team_side = str(p.get("team", "home")).lower()
            team_id = home_team_id if team_side == "home" else away_team_id
            player_name = str(p.get("player_name", f"Player {idx + 1}"))
            role_tag = str(p.get("role_tag", "CM")).upper()

            passes_baseline = self._safe_float(p.get("expected_passes_per_game"), 25.0)
            shots_baseline = self._safe_float(p.get("expected_shots_per_game"), 1.0)

            mapped_players.append({
                "player_id": f"{team_id.lower()}-{idx + 1}",
                "player_name": player_name,
                "team_id": team_id,
                "role_tag": role_tag,
                "expected_minutes": int(self._safe_float(p.get("expected_minutes"), 85)),
                "substitution_risk": str(p.get("substitution_risk", "medium")).lower(),
                "captain": bool(p.get("captain", False)),
                "is_lone_striker": bool(p.get("is_lone_striker", False)),
                "expected_passes_baseline": passes_baseline,
                "expected_shots_baseline": shots_baseline,
                "market_lines": {
                    "passes": round(passes_baseline * 0.9, 1),
                    "shots": round(shots_baseline * 0.9, 1),
                },
            })

        return {
            "source_timestamp_utc": _utc_now_z(),
            "teams": mapped_teams,
            "players": mapped_players,
        }

    @staticmethod
    def _safe_float(value: Any, default: float) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
