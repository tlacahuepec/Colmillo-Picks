"""Sport-agnostic grounding quality metrics for enrichment results."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any


_CONFIDENCE_MAP: dict[str, float] = {
    "high": 1.0,
    "medium": 0.66,
    "low": 0.33,
    "unknown": 0.0,
}

_NON_STAT_KEYS = frozenset(
    {"player_name", "name", "team", "position", "role", "sources", "is_starter", "rotation_risk"}
)


@dataclass(frozen=True)
class GroundingQualityReport:
    field_fill_rate: float
    source_url_presence_rate: float
    critical_null_rate: float
    confidence_score: float
    grounding_source_count: int
    web_search_query_count: int


def compute_field_fill_rate(
    players: list[dict[str, Any]],
    required_fields: dict[str, tuple[str, ...]],
) -> float:
    """Fraction of required fields that are non-null across all players."""
    all_required = _unique_required_fields(required_fields)
    if not players or not all_required:
        return 0.0

    total = 0
    populated = 0
    for player in players:
        for field in all_required:
            total += 1
            value = player.get(field)
            if value is not None:
                populated += 1

    return populated / total if total > 0 else 0.0


def compute_source_url_presence(players: list[dict[str, Any]]) -> float:
    """Fraction of player source entries that include a URL."""
    if not players:
        return 0.0

    total_sources = 0
    sources_with_url = 0
    for player in players:
        sources = player.get("sources", [])
        if not sources:
            continue
        for source in sources:
            total_sources += 1
            if source.get("url"):
                sources_with_url += 1

    return sources_with_url / total_sources if total_sources > 0 else 0.0


def compute_critical_null_rate(
    players: list[dict[str, Any]],
    required_fields: dict[str, tuple[str, ...]],
) -> float:
    """Fraction of critical (required) fields that are null or missing."""
    all_required = _unique_required_fields(required_fields)
    if not players or not all_required:
        return 0.0

    total = 0
    null_count = 0
    for player in players:
        for field in all_required:
            total += 1
            value = player.get(field)
            if value is None:
                null_count += 1

    return null_count / total if total > 0 else 0.0


def compute_consistency_score(results: list[dict[str, Any]]) -> float:
    """Mean coefficient of variation across numeric fields for the same player across attempts.

    Returns 0.0 when results are identical or insufficient for comparison.
    """
    if len(results) < 2:
        return 0.0

    field_values: dict[str, list[float]] = {}
    for result in results:
        for player in result.get("players", []):
            for key, value in player.items():
                if key in _NON_STAT_KEYS:
                    continue
                if isinstance(value, int | float) and value is not None:
                    field_values.setdefault(key, []).append(float(value))

    if not field_values:
        return 0.0

    cvs: list[float] = []
    for values in field_values.values():
        if len(values) < 2:
            continue
        mean = statistics.mean(values)
        if mean == 0:
            continue
        stdev = statistics.stdev(values)
        cvs.append(stdev / abs(mean))

    return statistics.mean(cvs) if cvs else 0.0


def score_enrichment_result(
    result: dict[str, Any],
    required_fields: dict[str, tuple[str, ...]],
    *,
    grounding_metadata: Any | None = None,
) -> GroundingQualityReport:
    """Compute a complete quality report for a single enrichment result."""
    players = result.get("players", [])
    confidence_raw = result.get("confidence", "unknown")
    confidence_score = _CONFIDENCE_MAP.get(confidence_raw.lower(), 0.0)

    grounding_source_count = 0
    web_search_query_count = 0
    if grounding_metadata is not None:
        grounding_source_count = len(getattr(grounding_metadata, "sources", ()))
        web_search_query_count = len(getattr(grounding_metadata, "web_search_queries", ()))

    return GroundingQualityReport(
        field_fill_rate=compute_field_fill_rate(players, required_fields),
        source_url_presence_rate=compute_source_url_presence(players),
        critical_null_rate=compute_critical_null_rate(players, required_fields),
        confidence_score=confidence_score,
        grounding_source_count=grounding_source_count,
        web_search_query_count=web_search_query_count,
    )


def _unique_required_fields(required_fields: dict[str, tuple[str, ...]]) -> list[str]:
    """Flatten and deduplicate required fields across all markets."""
    seen: set[str] = set()
    result: list[str] = []
    for fields in required_fields.values():
        for field in fields:
            if field not in seen:
                seen.add(field)
                result.append(field)
    return result
