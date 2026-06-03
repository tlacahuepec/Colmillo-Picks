"""Deterministic selection heuristic for best-of-N enrichment candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_CONFIDENCE_SCORES: dict[str, float] = {
    "high": 1.0,
    "medium": 0.5,
    "low": 0.25,
    "unknown": 0.0,
}

_NON_STAT_KEYS = frozenset({"name", "player_name", "team", "position", "role"})


@dataclass(frozen=True)
class EnrichmentCandidate:
    attempt: int
    temperature: float | None
    result: dict[str, Any]
    sources: list[Any]


@dataclass(frozen=True)
class SelectionDecision:
    winner_index: int
    attempt: int
    temperature: float | None
    reason: str
    populated_field_count: int
    avg_confidence: float
    critical_null_count: int


def _count_populated_and_nulls(
    candidate: EnrichmentCandidate,
    *,
    required_fields: dict[str, tuple[str, ...]] | None,
    requested_markets: tuple[str, ...],
) -> tuple[int, int]:
    players = candidate.result.get("players") or []
    if not players:
        return 0, 0

    if required_fields and requested_markets:
        target_fields: set[str] = set()
        for market in requested_markets:
            target_fields.update(required_fields.get(market, ()))
        if not target_fields:
            return _count_all_stats(players)
    else:
        return _count_all_stats(players)

    populated = 0
    nulls = 0
    for player in players:
        if not isinstance(player, dict):
            continue
        for field in target_fields:
            if player.get(field) is not None:
                populated += 1
            else:
                nulls += 1
    return populated, nulls


def _count_all_stats(players: list[Any]) -> tuple[int, int]:
    populated = 0
    nulls = 0
    for player in players:
        if not isinstance(player, dict):
            continue
        for key, value in player.items():
            if key in _NON_STAT_KEYS:
                continue
            if value is not None:
                populated += 1
            else:
                nulls += 1
    return populated, nulls


def _avg_confidence(candidate: EnrichmentCandidate) -> float:
    players = candidate.result.get("players") or []
    if not players:
        top_level = candidate.result.get("confidence", "unknown")
        return _CONFIDENCE_SCORES.get(str(top_level).lower(), 0.0)

    scores: list[float] = []
    for player in players:
        if not isinstance(player, dict):
            continue
        conf = str(player.get("confidence", candidate.result.get("confidence", "unknown"))).lower()
        scores.append(_CONFIDENCE_SCORES.get(conf, 0.0))

    if not scores:
        top_level = candidate.result.get("confidence", "unknown")
        return _CONFIDENCE_SCORES.get(str(top_level).lower(), 0.0)
    return sum(scores) / len(scores)


def select_best_enrichment(
    candidates: list[EnrichmentCandidate],
    *,
    required_fields: dict[str, tuple[str, ...]] | None = None,
    requested_markets: tuple[str, ...] = (),
) -> tuple[EnrichmentCandidate, SelectionDecision]:
    scored: list[tuple[int, int, float, int, EnrichmentCandidate]] = []
    for candidate in candidates:
        populated, nulls = _count_populated_and_nulls(
            candidate, required_fields=required_fields, requested_markets=requested_markets
        )
        confidence = _avg_confidence(candidate)
        scored.append((populated, nulls, confidence, candidate.attempt, candidate))

    scored.sort(key=lambda t: (-t[0], t[1], -t[2], t[3]))
    best = scored[0]
    populated, nulls, confidence, attempt, winner = best

    if len(scored) > 1:
        second = scored[1]
        if populated > second[0]:
            reason = "highest_populated_fields"
        elif nulls < second[1]:
            reason = "fewest_critical_nulls"
        elif confidence > second[2]:
            reason = "highest_confidence"
        else:
            reason = "first_attempt_preferred"
    else:
        reason = "only_candidate"

    decision = SelectionDecision(
        winner_index=candidates.index(winner),
        attempt=winner.attempt,
        temperature=winner.temperature,
        reason=reason,
        populated_field_count=populated,
        avg_confidence=round(confidence, 4),
        critical_null_count=nulls,
    )
    return winner, decision
