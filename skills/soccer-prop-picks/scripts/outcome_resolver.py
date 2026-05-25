"""Outcome resolution engine for settled picks.

Compares post-match stats against pick lines to determine win/loss/push/void,
then records results via the outcome recorder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from llm_post_match_stats import LLMPostMatchStatsProvider, PostMatchPlayerStat


class OutcomeRecorder(Protocol):
    """Protocol for recording resolved outcomes."""

    def __call__(self, pick_id: str, outcomes: list[dict[str, Any]]) -> Any: ...


@dataclass
class ResolutionResult:
    """Encapsulates a resolution outcome string."""

    value: str

    @classmethod
    def from_comparison(cls, *, actual: float | int, line: float, direction: str) -> str:
        if actual == line:
            return "push"
        if direction == "over":
            return "win" if actual > line else "loss"
        return "win" if actual < line else "loss"

    @classmethod
    def void(cls) -> str:
        return "void"


class OutcomeResolver:
    """Resolves pick outcomes using LLM-fetched post-match stats."""

    def __init__(
        self,
        *,
        stats_provider: LLMPostMatchStatsProvider,
        outcome_recorder: OutcomeRecorder,
    ) -> None:
        self._stats_provider = stats_provider
        self._outcome_recorder = outcome_recorder

    def resolve(
        self,
        *,
        pick_id: str,
        picks: list[dict[str, Any]],
        game_status: str | None = None,
    ) -> list[dict[str, Any]]:
        if game_status == "postponed":
            results = [
                {"rank": p["rank"], "player": p["player"], "market": p["market"], "result": "void"}
                for p in picks
            ]
            return results

        try:
            all_stats = self._stats_provider.fetch_player_stats(
                match_description=f"pick-{pick_id}",
                picks=picks,
            )
        except ValueError:
            return [
                {"rank": p["rank"], "player": p["player"], "market": p["market"], "result": "void"}
                for p in picks
            ]

        stats_by_key: dict[tuple[str, str], PostMatchPlayerStat] = {
            (s.player, s.market): s for s in all_stats
        }

        results: list[dict[str, Any]] = []
        for pick in picks:
            key = (pick["player"], pick["market"])
            stat = stats_by_key.get(key)

            if stat is None:
                results.append({
                    "rank": pick["rank"],
                    "player": pick["player"],
                    "market": pick["market"],
                    "result": ResolutionResult.void(),
                })
                continue

            if stat.confidence != "high":
                continue

            outcome = ResolutionResult.from_comparison(
                actual=stat.actual_value,
                line=pick["line"],
                direction=pick["direction"],
            )
            results.append({
                "rank": pick["rank"],
                "player": pick["player"],
                "market": pick["market"],
                "result": outcome,
            })

        if results:
            self._outcome_recorder(pick_id, results)

        return results
