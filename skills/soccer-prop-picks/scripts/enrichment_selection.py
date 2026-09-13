"""Deterministic selection heuristic for best-of-N enrichment candidates."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Any

from llm.client import GroundingMetadataResult

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
    grounding_metadata: GroundingMetadataResult | None = dataclass_field(default=None)


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


def _grounding_source_count(candidate: EnrichmentCandidate) -> int:
    if candidate.grounding_metadata is None:
        return 0
    return len(candidate.grounding_metadata.sources)


def select_best_enrichment(
    candidates: list[EnrichmentCandidate],
    *,
    required_fields: dict[str, tuple[str, ...]] | None = None,
    requested_markets: tuple[str, ...] = (),
    use_quality_tiebreaker: bool = False,
) -> tuple[EnrichmentCandidate, SelectionDecision]:
    scored: list[tuple[int, int, float, int, int, EnrichmentCandidate]] = []
    for candidate in candidates:
        populated, nulls = _count_populated_and_nulls(
            candidate, required_fields=required_fields, requested_markets=requested_markets
        )
        confidence = _avg_confidence(candidate)
        grounding_count = _grounding_source_count(candidate)
        scored.append((populated, nulls, confidence, grounding_count, candidate.attempt, candidate))

    scored.sort(key=lambda t: (-t[0], t[1], -t[2], -t[3], t[4]))
    best = scored[0]
    populated, nulls, confidence, grounding_count, attempt, winner = best

    reason = "only_candidate"
    if len(scored) > 1:
        second = scored[1]
        if populated > second[0]:
            reason = "highest_populated_fields"
        elif nulls < second[1]:
            reason = "fewest_critical_nulls"
        elif confidence > second[2]:
            reason = "highest_confidence"
        elif grounding_count > second[3]:
            reason = "most_grounding_sources"
        elif use_quality_tiebreaker and required_fields:
            winner, reason = _apply_quality_tiebreaker(scored, required_fields)
            populated, nulls, confidence = _stats_for(winner, scored)
        else:
            reason = "first_attempt_preferred"

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


def _stats_for(
    winner: EnrichmentCandidate,
    scored: list[tuple[int, int, float, int, int, EnrichmentCandidate]],
) -> tuple[int, int, float]:
    for populated, nulls, confidence, _, _, candidate in scored:
        if candidate is winner:
            return populated, nulls, confidence
    return 0, 0, 0.0


def _apply_quality_tiebreaker(
    scored: list[tuple[int, int, float, int, int, EnrichmentCandidate]],
    required_fields: dict[str, tuple[str, ...]],
) -> tuple[EnrichmentCandidate, str]:
    from grounding_quality_metrics import score_enrichment_result

    best_score = -1.0
    best_candidate = scored[0][5]
    for _, _, _, _, _, candidate in scored:
        report = score_enrichment_result(candidate.result, required_fields)
        quality = report.field_fill_rate + report.source_url_presence_rate + report.freshness_compliance
        if quality > best_score:
            best_score = quality
            best_candidate = candidate

    return best_candidate, "quality_tiebreaker"
