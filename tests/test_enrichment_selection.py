"""Tests for the enrichment selection heuristic (best-of-N winner picking)."""

from __future__ import annotations

from enrichment_selection import (
    EnrichmentCandidate,
    SelectionDecision,
    select_best_enrichment,
)


def _make_candidate(
    attempt: int,
    *,
    temperature: float | None = None,
    players: list | None = None,
    lines: dict | None = None,
    confidence: str = "medium",
) -> EnrichmentCandidate:
    return EnrichmentCandidate(
        attempt=attempt,
        temperature=temperature,
        result={
            "players": players or [],
            "lines": lines or {},
            "game": {},
            "confidence": confidence,
            "sources": [],
        },
        sources=[],
    )


def _player_with_fields(**fields: float | None) -> dict:
    return {"name": "Player A", **fields}


class TestSelectBestEnrichment:
    def test_selects_candidate_with_most_populated_fields(self) -> None:
        required = {"points": ("minutes_proj", "usage_rate", "points_avg", "points_last5")}
        sparse = _make_candidate(
            1,
            temperature=None,
            players=[_player_with_fields(minutes_proj=30.0, usage_rate=None, points_avg=None, points_last5=None)],
        )
        rich = _make_candidate(
            2,
            temperature=0.7,
            players=[_player_with_fields(minutes_proj=30.0, usage_rate=0.25, points_avg=22.1, points_last5=24.0)],
        )

        winner, decision = select_best_enrichment(
            [sparse, rich],
            required_fields=required,
            requested_markets=("points",),
        )

        assert winner.attempt == 2
        assert decision.reason == "highest_populated_fields"
        assert decision.populated_field_count == 4

    def test_first_attempt_wins_on_tie(self) -> None:
        required = {"points": ("minutes_proj",)}
        c1 = _make_candidate(1, temperature=None, players=[_player_with_fields(minutes_proj=30.0)])
        c2 = _make_candidate(2, temperature=0.7, players=[_player_with_fields(minutes_proj=32.0)])

        winner, decision = select_best_enrichment(
            [c1, c2],
            required_fields=required,
            requested_markets=("points",),
        )

        assert winner.attempt == 1

    def test_higher_confidence_breaks_tie(self) -> None:
        required = {"points": ("minutes_proj",)}
        c1 = _make_candidate(1, temperature=None, players=[_player_with_fields(minutes_proj=30.0)], confidence="low")
        c2 = _make_candidate(2, temperature=0.7, players=[_player_with_fields(minutes_proj=32.0)], confidence="high")

        winner, decision = select_best_enrichment(
            [c1, c2],
            required_fields=required,
            requested_markets=("points",),
        )

        assert winner.attempt == 2
        assert decision.reason == "highest_confidence"

    def test_fewer_critical_nulls_preferred(self) -> None:
        required = {"points": ("minutes_proj", "usage_rate", "points_avg")}
        c1 = _make_candidate(
            1,
            temperature=None,
            players=[_player_with_fields(minutes_proj=30.0, usage_rate=None, points_avg=20.0)],
        )
        c2 = _make_candidate(
            2,
            temperature=0.7,
            players=[_player_with_fields(minutes_proj=30.0, usage_rate=0.25, points_avg=20.0)],
        )

        winner, decision = select_best_enrichment(
            [c1, c2],
            required_fields=required,
            requested_markets=("points",),
        )

        assert winner.attempt == 2
        assert decision.critical_null_count == 0

    def test_single_candidate_returns_it(self) -> None:
        c = _make_candidate(1, temperature=None, players=[_player_with_fields(minutes_proj=30.0)])

        winner, decision = select_best_enrichment([c])

        assert winner.attempt == 1
        assert isinstance(decision, SelectionDecision)

    def test_all_empty_candidates_returns_first(self) -> None:
        c1 = _make_candidate(1, temperature=None, players=[])
        c2 = _make_candidate(2, temperature=0.7, players=[])

        winner, _ = select_best_enrichment([c1, c2])

        assert winner.attempt == 1

    def test_no_required_fields_counts_all_non_none_stats(self) -> None:
        sparse = _make_candidate(1, players=[_player_with_fields(minutes_proj=30.0)])
        rich = _make_candidate(
            2,
            temperature=0.7,
            players=[_player_with_fields(minutes_proj=30.0, usage_rate=0.25, points_avg=22.1)],
        )

        winner, decision = select_best_enrichment([sparse, rich])

        assert winner.attempt == 2
        assert decision.populated_field_count > 1


class TestQualityTiebreaker:
    def test_tiebreaker_selects_better_source_quality(self) -> None:
        """When populated counts are equal, quality tiebreaker picks better source quality."""
        required = {"points": ("minutes_proj", "usage_rate", "points_avg", "points_last5")}
        c1 = _make_candidate(
            1,
            temperature=None,
            players=[{
                "name": "Player A",
                "minutes_proj": 30.0,
                "usage_rate": 0.25,
                "points_avg": None,
                "points_last5": None,
                "sources": [{"label": "Unknown"}],
            }],
        )
        c2 = _make_candidate(
            2,
            temperature=0.7,
            players=[{
                "name": "Player A",
                "minutes_proj": 30.0,
                "usage_rate": 0.28,
                "points_avg": None,
                "points_last5": None,
                "sources": [{"label": "ESPN", "url": "https://espn.com/stats"}],
            }],
        )
        winner_default, _ = select_best_enrichment(
            [c1, c2],
            required_fields=required,
            requested_markets=("points",),
        )
        assert winner_default.attempt == 1

        winner_quality, decision = select_best_enrichment(
            [c1, c2],
            required_fields=required,
            requested_markets=("points",),
            use_quality_tiebreaker=True,
        )
        assert winner_quality.attempt == 2
        assert decision.reason == "quality_tiebreaker"

    def test_tiebreaker_off_by_default(self) -> None:
        """Default behavior unchanged — first attempt wins ties."""
        required = {"points": ("minutes_proj", "usage_rate")}
        c1 = _make_candidate(1, players=[_player_with_fields(minutes_proj=30.0, usage_rate=0.25)])
        c2 = _make_candidate(2, players=[_player_with_fields(minutes_proj=32.0, usage_rate=0.28)])

        winner, _ = select_best_enrichment(
            [c1, c2],
            required_fields=required,
            requested_markets=("points",),
        )
        assert winner.attempt == 1

    def test_tiebreaker_does_not_override_populated_count(self) -> None:
        """Quality tiebreaker only breaks ties — populated count still wins."""
        required = {"points": ("minutes_proj", "usage_rate", "points_avg", "points_last5")}
        sparse = _make_candidate(
            1,
            players=[_player_with_fields(minutes_proj=30.0)],
        )
        rich = _make_candidate(
            2,
            temperature=0.7,
            players=[_player_with_fields(minutes_proj=30.0, usage_rate=0.25, points_avg=22.0, points_last5=24.0)],
        )

        winner, decision = select_best_enrichment(
            [sparse, rich],
            required_fields=required,
            requested_markets=("points",),
            use_quality_tiebreaker=True,
        )
        assert winner.attempt == 2
        assert decision.reason == "highest_populated_fields"
