"""Deterministic priority and coverage tests for catalog events."""

from datetime import datetime, timezone

from services.catalog.contracts import CatalogEvent
from services.catalog.importance import ImportanceConfig, rank_events, score_event, select_important_events


NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)


def event(event_id, sport, league, start):
    return CatalogEvent(event_id, sport, league, start)


def test_score_is_bounded_explainable_and_deterministic():
    item = event("nfl:event:1", "nfl", "nfl", "2026-09-11T19:00:00Z")
    first = score_event(item, now=NOW, competition_type="playoff", market_count=10,
                        data_completeness=1, user_interest=5, rivalry=True)
    second = score_event(item, now=NOW, competition_type="playoff", market_count=10,
                         data_completeness=1, user_interest=5, rivalry=True)
    assert first == second
    assert 0 <= first[0] <= 100
    assert {"league:nfl", "competition:playoff", "starts_within_24h", "market_coverage",
            "data_complete", "user_interest", "rivalry"}.issubset(first[1])


def test_ranking_uses_stable_event_id_tie_breaker():
    items = [event("soccer:event:b", "soccer", "unknown", "unknown"),
             event("soccer:event:a", "soccer", "unknown", "unknown")]
    assert [item.event_id for item in rank_events(items, now=NOW)] == ["soccer:event:a", "soccer:event:b"]


def test_selection_preserves_each_sport_minimum_and_applies_caps():
    items = [event(f"{sport}:event:{number}", sport, "unknown", f"2026-09-11T{13 + number:02d}:00:00Z")
             for sport in ("nfl", "soccer", "mlb") for number in range(3)]
    config = ImportanceConfig({}, {}, per_sport_limit=2, minimum_per_sport=1)
    selected = select_important_events(items, config=config, score_kwargs={"now": NOW})
    assert {item.sport for item in selected} == {"nfl", "soccer", "mlb"}
    assert all(sum(item.sport == sport for item in selected) == 2 for sport in ("nfl", "soccer", "mlb"))
