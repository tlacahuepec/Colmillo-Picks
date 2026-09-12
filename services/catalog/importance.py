"""Deterministic event prioritization for the daily catalog job."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Iterable, Mapping

from services.catalog.contracts import CatalogEvent


@dataclass(frozen=True)
class ImportanceConfig:
    """Weights and caps used by one catalog preparation run."""

    league_weights: Mapping[str, float]
    competition_weights: Mapping[str, float]
    per_sport_limit: int = 20
    minimum_per_sport: int = 1


DEFAULT_IMPORTANCE_CONFIG = ImportanceConfig(
    league_weights={
        "nfl": 35.0,
        "nba": 35.0,
        "wnba": 30.0,
        "mlb": 35.0,
        "epl": 35.0,
        "la_liga": 32.0,
        "serie_a": 32.0,
        "bundesliga": 32.0,
        "ligue_1": 30.0,
    },
    competition_weights={
        "playoff": 20.0,
        "postseason": 20.0,
        "final": 20.0,
        "semifinal": 18.0,
        "regular": 10.0,
        "friendly": 2.0,
    },
)


def _hours_until(start_time: str, now: datetime) -> float | None:
    try:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return (start.astimezone(timezone.utc) - now.astimezone(timezone.utc)).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def score_event(
    event: CatalogEvent,
    *,
    config: ImportanceConfig = DEFAULT_IMPORTANCE_CONFIG,
    now: datetime | None = None,
    competition_type: str | None = None,
    market_count: int = 0,
    data_completeness: float = 0.0,
    user_interest: float = 0.0,
    rivalry: bool = False,
) -> tuple[float, tuple[str, ...]]:
    """Return a stable score in [0, 100] and human-readable score reasons."""
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    league = event.league.casefold()
    score = config.league_weights.get(league, 10.0)
    reasons.append(f"league:{league}")

    competition = (competition_type or "regular").casefold()
    competition_score = config.competition_weights.get(competition, 5.0)
    score += competition_score
    reasons.append(f"competition:{competition}")

    hours = _hours_until(event.start_time, now)
    if hours is not None:
        timing_score = 15.0 if 0 <= hours <= 24 else 10.0 if 24 < hours <= 72 else 4.0 if hours > 72 else 0.0
        score += timing_score
        reasons.append("starts_within_24h" if timing_score == 15.0 else "starts_within_72h" if timing_score == 10.0 else "scheduled")

    market_score = min(max(market_count, 0), 10) * 1.5
    score += market_score
    if market_count:
        reasons.append("market_coverage")

    completeness_score = min(max(data_completeness, 0.0), 1.0) * 10.0
    score += completeness_score
    if data_completeness >= 0.75:
        reasons.append("data_complete")

    interest_score = min(max(user_interest, 0.0), 5.0)
    score += interest_score
    if interest_score:
        reasons.append("user_interest")
    if rivalry:
        score += 5.0
        reasons.append("rivalry")

    return round(min(max(score, 0.0), 100.0), 3), tuple(reasons)


def rank_events(events: Iterable[CatalogEvent], **score_kwargs) -> list[CatalogEvent]:
    """Score and rank events with event ID as the stable final tie-breaker."""
    scored = []
    for event in events:
        score, reasons = score_event(event, **score_kwargs)
        scored.append(replace(event, importance_score=score, importance_reasons=reasons))
    return sorted(scored, key=lambda item: (-item.importance_score, item.start_time, item.event_id))


def select_important_events(events: Iterable[CatalogEvent], *, config: ImportanceConfig = DEFAULT_IMPORTANCE_CONFIG,
                            score_kwargs: Mapping[str, object] | None = None) -> list[CatalogEvent]:
    """Apply per-sport minimum coverage and then configurable per-sport limits."""
    ranked = rank_events(events, config=config, **(dict(score_kwargs or {})))
    by_sport: dict[str, list[CatalogEvent]] = {}
    for event in ranked:
        by_sport.setdefault(event.sport, []).append(event)
    selected: list[CatalogEvent] = []
    for sport in sorted(by_sport):
        selected.extend(by_sport[sport][:max(config.minimum_per_sport, 0)])
    selected_ids = {event.event_id for event in selected}
    for event in ranked:
        sport_count = sum(item.sport == event.sport for item in selected)
        if event.event_id not in selected_ids and sport_count < config.per_sport_limit:
            selected.append(event)
            selected_ids.add(event.event_id)
    return sorted(selected, key=lambda item: (-item.importance_score, item.start_time, item.event_id))
