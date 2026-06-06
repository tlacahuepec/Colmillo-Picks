"""Tests for Sports Stats Bible documentation completeness."""

from __future__ import annotations

from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _ROOT / "docs"


class TestSportsStatsBibleExists:
    @pytest.fixture
    def bible(self) -> str:
        path = _DOCS / "sports-stats-bible.md"
        assert path.exists(), f"Missing {path}"
        return path.read_text(encoding="utf-8")

    def test_has_purpose_section(self, bible):
        assert "## Purpose" in bible

    def test_has_free_only_constraint(self, bible):
        assert "no paid subscriptions" in bible.lower()

    def test_has_current_architecture_section(self, bible):
        assert "## Current architecture reality" in bible

    def test_has_outlier_target_section(self, bible):
        assert "## Outlier-style target product" in bible

    def test_has_practical_approximation_section(self, bible):
        assert "## Practical approximation of Outlier capabilities" in bible

    def test_has_source_tiers_section(self, bible):
        assert "## Source tiers" in bible

    def test_has_key_metrics_glossary(self, bible):
        assert "## Key Metrics Glossary" in bible

    def test_has_basketball_source_matrix(self, bible):
        assert "## Basketball source matrix" in bible

    def test_has_soccer_source_matrix(self, bible):
        assert "## Soccer source matrix" in bible

    def test_has_baseball_source_matrix(self, bible):
        assert "## Baseball source matrix" in bible

    def test_has_betting_source_matrix(self, bible):
        assert "## Betting and props source matrix" in bible

    def test_has_field_dictionary(self, bible):
        assert "## Field dictionary" in bible

    def test_has_grounding_recipes(self, bible):
        assert "## LLM grounding recipes" in bible

    def test_has_example_grounding_patterns(self, bible):
        assert "### Example grounding query patterns" in bible

    def test_has_anti_patterns_section(self, bible):
        assert "## Anti-patterns and grounding quality rules" in bible

    def test_has_implementation_roadmap(self, bible):
        assert "## Implementation roadmap" in bible

    def test_has_contribute_section(self, bible):
        assert "## How to contribute to this Bible" in bible


class TestSportsStatsBibleURLExamples:
    @pytest.fixture
    def bible(self) -> str:
        path = _DOCS / "sports-stats-bible.md"
        return path.read_text(encoding="utf-8")

    def test_has_espn_gamelog_url(self, bible):
        assert "espn.com/nba/player/gamelog" in bible

    def test_has_statmuse_url(self, bible):
        assert "statmuse.com/nba/ask" in bible

    def test_has_fotmob_url(self, bible):
        assert "fotmob.com/players" in bible

    def test_has_fbref_url(self, bible):
        assert "fbref.com/en/players" in bible

    def test_has_transfermarkt_url(self, bible):
        assert "transfermarkt.com" in bible

    def test_has_sofascore_url(self, bible):
        assert "sofascore.com/player" in bible

    def test_has_nba_com_url(self, bible):
        assert "nba.com/stats/player" in bible


class TestSportsStatsBibleContent:
    @pytest.fixture
    def bible(self) -> str:
        path = _DOCS / "sports-stats-bible.md"
        return path.read_text(encoding="utf-8")

    def test_mentions_gemini_grounding(self, bible):
        assert "gemini" in bible.lower()

    def test_mentions_mlb_statsapi(self, bible):
        assert "MLB StatsAPI" in bible

    def test_mentions_prizepicks(self, bible):
        assert "PrizePicks" in bible

    def test_has_tier_0_direct_adapter(self, bible):
        assert "Direct adapter" in bible

    def test_has_budget_rule(self, bible):
        assert "Budget rule" in bible

    def test_glossary_defines_usage_rate(self, bible):
        assert "Usage Rate (USG%)" in bible

    def test_glossary_defines_xg(self, bible):
        assert "Expected Goals (xG)" in bible

    def test_anti_pattern_no_fabrication(self, bible):
        assert "No fabrication" in bible

    def test_anti_pattern_cross_check_injuries(self, bible):
        assert "cross-check" in bible.lower() or "Cross-check" in bible
