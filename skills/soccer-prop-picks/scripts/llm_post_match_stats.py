"""LLM-based post-match stats provider for outcome resolution.

Queries an LLM with search grounding to fetch verified final box score
statistics for players in settled picks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class LLMClient(Protocol):
    """Minimal protocol for structured LLM output."""

    def generate_structured(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class PostMatchPlayerStat:
    player: str
    market: str
    actual_value: float | int
    confidence: str


_CONFIDENCE_LEVELS = ("low", "medium", "high")

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "stats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "player": {"type": "string"},
                    "market": {"type": "string"},
                    "actual_value": {"type": "number"},
                    "confidence": {"type": "string", "enum": list(_CONFIDENCE_LEVELS)},
                },
                "required": ["player", "market", "actual_value", "confidence"],
            },
        }
    },
    "required": ["stats"],
}


def build_stats_prompt(*, match_description: str, picks: list[dict[str, Any]]) -> str:
    """Build the LLM prompt requesting post-match stats for given picks."""
    lines = [
        f"Match: {match_description}",
        "",
        "For each player/market below, provide the FINAL official box score stat.",
        "Include a confidence level (low, medium, high) based on source reliability.",
        "",
        "Players and markets:",
    ]
    for pick in picks:
        lines.append(f"  - {pick['player']} — {pick['market']}")

    lines.extend([
        "",
        "Return structured JSON with an array of stats objects.",
        "Each object must include: player, market, actual_value, confidence.",
    ])
    return "\n".join(lines)


class LLMPostMatchStatsProvider:
    """Fetches post-match player statistics via LLM with search grounding."""

    def __init__(self, *, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def fetch_player_stats(
        self,
        *,
        match_description: str,
        picks: list[dict[str, Any]],
        min_confidence: str | None = None,
    ) -> list[PostMatchPlayerStat]:
        if not picks:
            return []

        prompt = build_stats_prompt(match_description=match_description, picks=picks)
        raw = self._llm_client.generate_structured(prompt, _RESPONSE_SCHEMA)

        stats = [
            PostMatchPlayerStat(
                player=item["player"],
                market=item["market"],
                actual_value=item["actual_value"],
                confidence=item["confidence"],
            )
            for item in raw.get("stats", [])
        ]

        if min_confidence is not None:
            min_idx = _CONFIDENCE_LEVELS.index(min_confidence)
            stats = [s for s in stats if _CONFIDENCE_LEVELS.index(s.confidence) >= min_idx]

        return stats
