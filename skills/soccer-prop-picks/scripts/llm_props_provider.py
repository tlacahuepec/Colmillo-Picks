"""LLM-powered NBA prop lines provider using search grounding."""

from __future__ import annotations

import json
import os
import statistics
import sys
from datetime import datetime, timezone
from typing import Any

from llm.client import LLMClient


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class LLMPropsProvider:
    """Fetches NBA player prop lines from sportsbooks via an LLM with search grounding."""

    def __init__(self, *, client: LLMClient) -> None:
        self._client = client
        self.last_sources: list = []

    def get_prop_lines(
        self,
        *,
        players: list[dict[str, Any]],
        markets: tuple[str, ...],
    ) -> dict[str, dict[str, Any]] | None:
        debug = os.getenv("COLMILLO_PROPS_LLM_DEBUG", "").strip() not in ("", "0", "false")
        try:
            result = self._client.generate_structured(
                system_prompt=self._build_system_prompt(),
                user_prompt=self._build_user_prompt(players=players, markets=markets),
                schema={},
            )
            self.last_sources = list(getattr(self._client, "last_sources", []))
            if debug:
                print(
                    f"[props-llm-debug] response: {json.dumps(result, default=str)[:2000]}",
                    file=sys.stderr,
                )
            return self._map_response(result)
        except Exception as exc:
            if debug:
                print(
                    f"[props-llm-debug] error: {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
            return None

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You provide NBA player prop lines from major sportsbooks for a betting-analysis pipeline. "
            "Use current or live prop lines when available. "
            "Return exactly one JSON object. Do not include markdown or prose."
        )

    @staticmethod
    def _build_user_prompt(
        *, players: list[dict[str, Any]], markets: tuple[str, ...],
    ) -> str:
        player_names = [p.get("player_name", "") for p in players if p.get("player_name")]
        return json.dumps(
            {
                "task": "Provide current NBA player prop lines from sportsbooks.",
                "today_utc": _utc_now_z(),
                "request": {
                    "players": player_names,
                    "markets": list(markets),
                    "sportsbooks": ["PrizePicks", "DraftKings", "FanDuel"],
                },
                "required_json_shape": {
                    "players": {
                        "<player_name>": {
                            "<market>": [
                                {"source": "sportsbook name", "line": 25.5},
                            ]
                        }
                    }
                },
                "rules": [
                    "Include prop lines from at least 3 sportsbooks (PrizePicks, DraftKings, FanDuel).",
                    "For each player, provide lines for each requested market.",
                    "Use the over/under line value (e.g., 25.5 for points over/under 25.5).",
                    "Use real current prop lines from today or the most recent available.",
                    "If a line is not available from a sportsbook, omit that entry.",
                    "Return JSON only — no markdown, no prose.",
                ],
            },
            sort_keys=True,
        )

    def _map_response(self, result: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
        raw_players = result.get("players", {})
        if not isinstance(raw_players, dict) or not raw_players:
            return None

        mapped: dict[str, dict[str, Any]] = {}
        for player_name, markets_data in raw_players.items():
            if not isinstance(markets_data, dict):
                continue
            player_markets: dict[str, Any] = {}
            for market, lines_list in markets_data.items():
                if not isinstance(lines_list, list):
                    continue
                lines: list[float] = []
                sources: list[dict[str, Any]] = []
                for entry in lines_list:
                    if not isinstance(entry, dict):
                        continue
                    line_val = self._safe_float(entry.get("line"))
                    if line_val is None:
                        continue
                    lines.append(line_val)
                    sources.append({
                        "source": str(entry.get("source", "unknown")),
                        "line": line_val,
                    })
                if lines:
                    consensus_line = float(sorted(lines)[len(lines) // 2])
                    player_markets[market] = {
                        "line": consensus_line,
                        "market_agreement": self._compute_market_agreement(lines),
                        "sources": sources,
                    }
            if player_markets:
                mapped[str(player_name)] = player_markets

        return mapped if mapped else None

    @staticmethod
    def _compute_market_agreement(lines: list[float]) -> float:
        if not lines:
            return 0.0
        if len(lines) == 1:
            return 1.0
        mean = statistics.mean(lines)
        if mean == 0:
            return 0.0
        std_dev = statistics.stdev(lines)
        agreement = 1.0 - (std_dev / mean)
        return max(0.0, min(1.0, round(agreement, 4)))

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
