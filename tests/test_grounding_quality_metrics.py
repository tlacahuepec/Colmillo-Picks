"""Tests for grounding quality metrics computation."""

from __future__ import annotations

import pytest

from grounding_quality_metrics import (
    GroundingQualityReport,
    compute_critical_null_rate,
    compute_field_fill_rate,
    compute_freshness_compliance,
    compute_source_url_presence,
    compute_consistency_score,
    score_enrichment_result,
)


_BASKETBALL_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "points": ("minutes_proj", "usage_rate", "points_avg", "points_last5"),
    "rebounds": ("minutes_proj", "usage_rate", "rebound_avg", "rebound_last5"),
    "assists": ("minutes_proj", "usage_rate", "assist_avg", "assist_last5"),
    "threes": (
        "minutes_proj",
        "usage_rate",
        "threes_avg",
        "threes_last5",
        "three_point_attempts",
    ),
}


class TestComputeFieldFillRate:
    def test_all_populated(self):
        players = [
            {
                "player_name": "LeBron James",
                "minutes_proj": 35.0,
                "usage_rate": 0.28,
                "points_avg": 25.5,
                "points_last5": 27.0,
                "rebound_avg": 7.5,
                "rebound_last5": 8.0,
                "assist_avg": 7.2,
                "assist_last5": 7.8,
                "threes_avg": 2.3,
                "threes_last5": 2.5,
                "three_point_attempts": 5.5,
            }
        ]
        rate = compute_field_fill_rate(players, _BASKETBALL_REQUIRED_FIELDS)
        assert rate == 1.0

    def test_half_null(self):
        players = [
            {
                "player_name": "Test Player",
                "minutes_proj": 30.0,
                "usage_rate": None,
                "points_avg": 20.0,
                "points_last5": None,
                "rebound_avg": 5.0,
                "rebound_last5": None,
                "assist_avg": 4.0,
                "assist_last5": None,
                "threes_avg": 1.5,
                "threes_last5": None,
                "three_point_attempts": None,
            }
        ]
        rate = compute_field_fill_rate(players, _BASKETBALL_REQUIRED_FIELDS)
        assert rate == pytest.approx(5 / 11)

    def test_empty_players(self):
        rate = compute_field_fill_rate([], _BASKETBALL_REQUIRED_FIELDS)
        assert rate == 0.0

    def test_missing_fields_treated_as_null(self):
        players = [{"player_name": "Sparse Player", "minutes_proj": 32.0}]
        rate = compute_field_fill_rate(players, _BASKETBALL_REQUIRED_FIELDS)
        assert rate == pytest.approx(1 / 11)


class TestComputeSourceUrlPresence:
    def test_all_have_urls(self):
        players = [
            {
                "player_name": "LeBron James",
                "sources": [
                    {"label": "ESPN", "url": "https://espn.com/player/1"},
                    {"label": "StatMuse", "url": "https://statmuse.com/q"},
                ],
            }
        ]
        rate = compute_source_url_presence(players)
        assert rate == 1.0

    def test_no_urls(self):
        players = [
            {
                "player_name": "LeBron James",
                "sources": [{"label": "ESPN"}],
            }
        ]
        rate = compute_source_url_presence(players)
        assert rate == 0.0

    def test_no_sources_key(self):
        players = [{"player_name": "LeBron James"}]
        rate = compute_source_url_presence(players)
        assert rate == 0.0

    def test_empty_players(self):
        rate = compute_source_url_presence([])
        assert rate == 0.0

    def test_mixed_urls(self):
        players = [
            {
                "player_name": "Player A",
                "sources": [
                    {"label": "ESPN", "url": "https://espn.com/x"},
                    {"label": "Unknown"},
                ],
            }
        ]
        rate = compute_source_url_presence(players)
        assert rate == pytest.approx(0.5)


class TestComputeCriticalNullRate:
    def test_no_nulls(self):
        players = [
            {
                "player_name": "LeBron James",
                "minutes_proj": 35.0,
                "usage_rate": 0.28,
                "points_avg": 25.5,
                "points_last5": 27.0,
            }
        ]
        required = {"points": ("minutes_proj", "usage_rate", "points_avg", "points_last5")}
        rate = compute_critical_null_rate(players, required)
        assert rate == 0.0

    def test_all_null(self):
        players = [
            {
                "player_name": "LeBron James",
                "minutes_proj": None,
                "usage_rate": None,
                "points_avg": None,
                "points_last5": None,
            }
        ]
        required = {"points": ("minutes_proj", "usage_rate", "points_avg", "points_last5")}
        rate = compute_critical_null_rate(players, required)
        assert rate == 1.0

    def test_partial_nulls(self):
        players = [
            {
                "player_name": "Test",
                "minutes_proj": 30.0,
                "usage_rate": None,
                "points_avg": 20.0,
                "points_last5": None,
            }
        ]
        required = {"points": ("minutes_proj", "usage_rate", "points_avg", "points_last5")}
        rate = compute_critical_null_rate(players, required)
        assert rate == pytest.approx(0.5)


class TestComputeConsistencyScore:
    def test_identical_results(self):
        results = [
            {"players": [{"player_name": "A", "points_last5": 25.0, "usage_rate": 0.30}]},
            {"players": [{"player_name": "A", "points_last5": 25.0, "usage_rate": 0.30}]},
            {"players": [{"player_name": "A", "points_last5": 25.0, "usage_rate": 0.30}]},
        ]
        score = compute_consistency_score(results)
        assert score == 0.0

    def test_different_results(self):
        results = [
            {"players": [{"player_name": "A", "points_last5": 20.0}]},
            {"players": [{"player_name": "A", "points_last5": 25.0}]},
            {"players": [{"player_name": "A", "points_last5": 30.0}]},
        ]
        score = compute_consistency_score(results)
        assert score > 0.0

    def test_empty_results(self):
        score = compute_consistency_score([])
        assert score == 0.0

    def test_single_result(self):
        results = [{"players": [{"player_name": "A", "points_last5": 25.0}]}]
        score = compute_consistency_score(results)
        assert score == 0.0


class TestScoreEnrichmentResult:
    def test_full_result(self):
        result = {
            "players": [
                {
                    "player_name": "LeBron James",
                    "minutes_proj": 35.0,
                    "usage_rate": 0.28,
                    "points_avg": 25.5,
                    "points_last5": 27.0,
                    "rebound_avg": 7.5,
                    "rebound_last5": 8.0,
                    "assist_avg": 7.2,
                    "assist_last5": 7.8,
                    "threes_avg": 2.3,
                    "threes_last5": 2.5,
                    "three_point_attempts": 5.5,
                    "sources": [
                        {"label": "ESPN", "url": "https://espn.com/x"},
                        {"label": "NBA.com", "url": "https://nba.com/y"},
                    ],
                }
            ],
            "confidence": "high",
            "sources": [{"label": "Search", "url": "https://example.com"}],
        }
        report = score_enrichment_result(result, _BASKETBALL_REQUIRED_FIELDS)
        assert isinstance(report, GroundingQualityReport)
        assert report.field_fill_rate == 1.0
        assert report.source_url_presence_rate == 1.0
        assert report.critical_null_rate == 0.0
        assert report.confidence_score == 1.0

    def test_empty_result(self):
        result = {"players": [], "confidence": "unknown", "sources": []}
        report = score_enrichment_result(result, _BASKETBALL_REQUIRED_FIELDS)
        assert report.field_fill_rate == 0.0
        assert report.confidence_score == 0.0

    def test_with_grounding_metadata(self):
        result = {
            "players": [
                {
                    "player_name": "Test",
                    "minutes_proj": 30.0,
                    "sources": [{"label": "X", "url": "https://x.com"}],
                }
            ],
            "confidence": "medium",
            "sources": [],
        }
        from llm.client import GroundingMetadataResult, GroundingSource

        metadata = GroundingMetadataResult(
            sources=(
                GroundingSource(url="https://espn.com/a", title="ESPN"),
                GroundingSource(url="https://nba.com/b", title="NBA"),
            ),
            supports=(),
            web_search_queries=("LeBron James stats", "LeBron last 5 games"),
        )
        report = score_enrichment_result(
            result, _BASKETBALL_REQUIRED_FIELDS, grounding_metadata=metadata
        )
        assert report.grounding_source_count == 2
        assert report.web_search_query_count == 2
        assert report.confidence_score == pytest.approx(0.66, abs=0.01)


class TestComputeFreshnessCompliance:
    def test_no_sources_returns_default(self):
        players = [{"player_name": "Test", "minutes_proj": 30.0}]
        rate = compute_freshness_compliance(players)
        assert rate == 1.0

    def test_all_fresh_sources(self):
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc).isoformat()
        players = [
            {
                "player_name": "Test",
                "sources": [
                    {"label": "ESPN", "url": "https://espn.com", "retrieved_at": now},
                    {"label": "NBA", "url": "https://nba.com", "retrieved_at": now},
                ],
            }
        ]
        rate = compute_freshness_compliance(players, ttl_days=7)
        assert rate == 1.0

    def test_all_stale_sources(self):
        players = [
            {
                "player_name": "Test",
                "sources": [
                    {"label": "ESPN", "url": "https://espn.com", "retrieved_at": "2020-01-01T00:00:00+00:00"},
                    {"label": "NBA", "url": "https://nba.com", "retrieved_at": "2020-01-02T00:00:00+00:00"},
                ],
            }
        ]
        rate = compute_freshness_compliance(players, ttl_days=7)
        assert rate == 0.0

    def test_mixed_freshness(self):
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc).isoformat()
        players = [
            {
                "player_name": "Test",
                "sources": [
                    {"label": "Fresh", "url": "https://x.com", "retrieved_at": now},
                    {"label": "Stale", "url": "https://y.com", "retrieved_at": "2020-01-01T00:00:00+00:00"},
                ],
            }
        ]
        rate = compute_freshness_compliance(players, ttl_days=7)
        assert rate == pytest.approx(0.5)

    def test_sources_without_timestamp_are_fresh(self):
        players = [
            {
                "player_name": "Test",
                "sources": [
                    {"label": "ESPN", "url": "https://espn.com"},
                ],
            }
        ]
        rate = compute_freshness_compliance(players, ttl_days=7)
        assert rate == 1.0


_BASEBALL_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "hits": ("batting_avg", "hits_last5", "at_bats_avg"),
    "total_bases": ("batting_avg", "slugging_pct", "total_bases_last5"),
    "runs": ("batting_avg", "runs_last5", "obp"),
    "rbi": ("batting_avg", "rbi_last5", "runners_in_scoring_position_avg"),
    "strikeouts": ("k_rate", "strikeouts_last5", "pitcher_k_rate"),
}


class TestBaseballFieldScoring:
    def test_full_baseball_result(self):
        result = {
            "players": [
                {
                    "player_name": "Aaron Judge",
                    "batting_avg": 0.310,
                    "hits_last5": 1.8,
                    "at_bats_avg": 4.2,
                    "slugging_pct": 0.650,
                    "total_bases_last5": 3.0,
                    "runs_last5": 1.2,
                    "obp": 0.420,
                    "rbi_last5": 1.5,
                    "runners_in_scoring_position_avg": 0.340,
                    "k_rate": 0.28,
                    "strikeouts_last5": 1.6,
                    "pitcher_k_rate": 0.25,
                    "sources": [{"label": "ESPN", "url": "https://espn.com/mlb"}],
                }
            ],
            "confidence": "high",
            "sources": [],
        }
        report = score_enrichment_result(result, _BASEBALL_REQUIRED_FIELDS)
        assert report.field_fill_rate == 1.0
        assert report.critical_null_rate == 0.0
        assert report.source_url_presence_rate == 1.0

    def test_partial_baseball_result(self):
        result = {
            "players": [
                {
                    "player_name": "Aaron Judge",
                    "batting_avg": 0.310,
                    "hits_last5": None,
                    "at_bats_avg": None,
                    "slugging_pct": 0.650,
                    "total_bases_last5": None,
                    "sources": [],
                }
            ],
            "confidence": "medium",
            "sources": [],
        }
        report = score_enrichment_result(result, _BASEBALL_REQUIRED_FIELDS)
        assert report.field_fill_rate < 1.0
        assert report.critical_null_rate > 0.0

    def test_empty_baseball_result(self):
        result = {"players": [], "confidence": "unknown", "sources": []}
        report = score_enrichment_result(result, _BASEBALL_REQUIRED_FIELDS)
        assert report.field_fill_rate == 0.0

    def test_baseball_uses_same_function_as_basketball(self):
        basketball_result = {
            "players": [{"player_name": "Test", "minutes_proj": 30.0}],
            "confidence": "high",
            "sources": [],
        }
        baseball_result = {
            "players": [{"player_name": "Test", "batting_avg": 0.300}],
            "confidence": "high",
            "sources": [],
        }
        bball_report = score_enrichment_result(basketball_result, _BASKETBALL_REQUIRED_FIELDS)
        base_report = score_enrichment_result(baseball_result, _BASEBALL_REQUIRED_FIELDS)
        assert isinstance(bball_report, GroundingQualityReport)
        assert isinstance(base_report, GroundingQualityReport)


class TestScoreEnrichmentResultIncludesFreshness:
    def test_report_has_freshness_field(self):
        result = {
            "players": [
                {
                    "player_name": "Test",
                    "minutes_proj": 30.0,
                    "sources": [{"label": "X", "url": "https://x.com"}],
                }
            ],
            "confidence": "high",
            "sources": [],
        }
        report = score_enrichment_result(result, _BASKETBALL_REQUIRED_FIELDS)
        assert hasattr(report, "freshness_compliance")
        assert report.freshness_compliance == 1.0
