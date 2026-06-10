"""LLM-powered NBA player stats provider using search grounding."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from llm.client import LLMClient

logger = logging.getLogger("colmillo.basketball")


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class LLMPlayerStatsProvider:
    """Fetches NBA player season/recent stats via an LLM with search grounding."""

    def __init__(self, *, client: LLMClient) -> None:
        self._client = client
        self.last_sources: list = []
        self.last_grounding_metadata = None

    def get_player_stats(
        self, *, home_team: str, away_team: str, match_date: str,
    ) -> list[dict[str, Any]] | None:
        debug = os.getenv("COLMILLO_PLAYER_STATS_LLM_DEBUG", "").strip() not in ("", "0", "false")
        try:
            result = self._client.generate_structured(
                system_prompt=self._build_system_prompt(),
                user_prompt=self._build_user_prompt(
                    home_team=home_team, away_team=away_team, match_date=match_date,
                ),
                schema={},
            )
            self.last_sources = list(getattr(self._client, "last_sources", []))
            self.last_grounding_metadata = getattr(self._client, "last_grounding_metadata", None)
            if debug:
                print(
                    f"[player-stats-llm-debug] response: {json.dumps(result, default=str)[:2000]}",
                    file=sys.stderr,
                )
            mapped = self._map_response(result)
            if mapped is None:
                logger.warning(
                    "basketball_player_stats_empty_response",
                    extra={
                        "home_team": home_team,
                        "away_team": away_team,
                        "match_date": match_date,
                        "raw_keys": list(result.keys()) if isinstance(result, dict) else str(type(result)),
                    },
                )
            else:
                logger.info(
                    "basketball_player_stats_fetched",
                    extra={
                        "home_team": home_team,
                        "away_team": away_team,
                        "player_count": len(mapped),
                    },
                )
            return mapped
        except Exception as exc:
            logger.warning(
                "basketball_player_stats_llm_error",
                extra={
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                },
            )
            if debug:
                print(
                    f"[player-stats-llm-debug] error: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
            return None

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You provide NBA basketball player statistics for a betting-analysis pipeline. "
            "Use current season data when available. "
            "Return exactly one JSON object. Do not include markdown or prose."
        )

    @staticmethod
    def _build_user_prompt(
        *, home_team: str, away_team: str, match_date: str,
    ) -> str:
        return json.dumps(
            {
                "task": "Provide NBA player stats for key players in this matchup.",
                "today_utc": _utc_now_z(),
                "request": {
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                    "league": "NBA",
                },
                "required_json_shape": {
                    "players": [
                        {
                            "player_name": "full name",
                            "team": "3-letter team code",
                            "position": "PG|SG|SF|PF|C",
                            "minutes_proj": "projected minutes (float)",
                            "usage_rate": "usage rate 0-1 (float)",
                            "points_avg": "season points per game (float)",
                            "points_last5": "last 5 games points avg (float)",
                            "assist_avg": "season assists per game (float)",
                            "assist_last5": "last 5 games assists avg (float)",
                            "rebound_avg": "season rebounds per game (float)",
                            "rebound_last5": "last 5 games rebounds avg (float)",
                            "threes_avg": "season 3PM per game (float)",
                            "threes_last5": "last 5 games 3PM avg (float)",
                            "three_point_attempts": "3PA per game (float)",
                            "steals_avg": "season steals per game (float)",
                            "steals_last5": "last 5 games steals avg (float)",
                            "blocks_avg": "season blocks per game (float)",
                            "blocks_last5": "last 5 games blocks avg (float)",
                            "turnovers_avg": "season turnovers per game (float)",
                            "turnovers_last5": "last 5 games turnovers avg (float)",
                            "fg_made_avg": "season FG made per game (float)",
                            "fg_made_last5": "last 5 games FG made avg (float)",
                            "fg_attempted_avg": "season FGA per game (float)",
                            "fg_attempted_last5": "last 5 games FGA avg (float)",
                            "two_pt_made_avg": "season 2PT FG made per game (float)",
                            "two_pt_made_last5": "last 5 games 2PT FG made avg (float)",
                            "rotation_risk": "locked_in|normal|elevated|high",
                            "injury_status": "healthy|questionable|doubtful|out",
                            "is_starter": "true|false",
                        }
                    ]
                },
                "rules": [
                    "Include exactly 8 players: 4 from the home team and 4 from the away team.",
                    "Select the top 4 players per team by usage rate who are expected to play (starters preferred).",
                    "CRITICAL: Only include players on the team's CURRENT active roster as of today. Players who were traded, waived, released, or sent to G-League before today MUST NOT be included.",
                    "If uncertain whether a player is currently on the team, exclude them and include a different active roster player instead.",
                    "Use current-season statistics, not career averages.",
                    "Last 5 game averages should be from the most recent 5 games played.",
                    "Projected minutes should reflect the player's typical workload this season.",
                    "Usage rate is the percentage of team plays used by the player (0.15-0.35 typical range).",
                    "Rotation risk: locked_in=star starter, normal=regular starter, elevated=minutes fluctuating, high=bench player or injury concern.",
                    "CRITICAL: Do NOT return null for usage_rate, minutes_proj, points_avg, or rebound_avg — these are required. If you cannot find a value, estimate from available data.",
                    "Use null only for fields you truly cannot determine with reasonable confidence.",
                    "Return JSON only — no markdown, no prose.",
                ],
            },
            sort_keys=True,
        )

    def _map_response(self, result: dict[str, Any]) -> list[dict[str, Any]] | None:
        raw_players = result.get("players", [])
        if not isinstance(raw_players, list) or not raw_players:
            return None

        mapped: list[dict[str, Any]] = []
        for p in raw_players:
            if not isinstance(p, dict):
                continue
            player_name = str(p.get("player_name", "")).strip()
            if not player_name:
                continue
            mapped.append({
                "player_name": player_name,
                "team": str(p.get("team", "UNK")),
                "position": str(p.get("position", "SF")),
                "minutes_proj": self._safe_float(p.get("minutes_proj")),
                "usage_rate": self._safe_float(p.get("usage_rate")),
                "points_avg": self._safe_float(p.get("points_avg")),
                "points_last5": self._safe_float(p.get("points_last5")),
                "assist_avg": self._safe_float(p.get("assist_avg")),
                "assist_last5": self._safe_float(p.get("assist_last5")),
                "rebound_avg": self._safe_float(p.get("rebound_avg")),
                "rebound_last5": self._safe_float(p.get("rebound_last5")),
                "threes_avg": self._safe_float(p.get("threes_avg")),
                "threes_last5": self._safe_float(p.get("threes_last5")),
                "three_point_attempts": self._safe_float(p.get("three_point_attempts")),
                "steals_avg": self._safe_float(p.get("steals_avg")),
                "steals_last5": self._safe_float(p.get("steals_last5")),
                "blocks_avg": self._safe_float(p.get("blocks_avg")),
                "blocks_last5": self._safe_float(p.get("blocks_last5")),
                "turnovers_avg": self._safe_float(p.get("turnovers_avg")),
                "turnovers_last5": self._safe_float(p.get("turnovers_last5")),
                "fg_made_avg": self._safe_float(p.get("fg_made_avg")),
                "fg_made_last5": self._safe_float(p.get("fg_made_last5")),
                "fg_attempted_avg": self._safe_float(p.get("fg_attempted_avg")),
                "fg_attempted_last5": self._safe_float(p.get("fg_attempted_last5")),
                "two_pt_made_avg": self._safe_float(p.get("two_pt_made_avg")),
                "two_pt_made_last5": self._safe_float(p.get("two_pt_made_last5")),
                "rotation_risk": self._safe_str(p.get("rotation_risk"), "normal"),
                "injury_status": self._safe_str(p.get("injury_status"), "healthy"),
                "is_starter": bool(p.get("is_starter", True)),
            })

        return mapped if mapped else None

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_str(value: Any, default: str) -> str:
        if value is None:
            return default
        s = str(value).strip().lower()
        return s if s else default
