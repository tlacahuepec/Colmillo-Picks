"""Tests for the Sports Stats Bible documentation."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "sports-stats-bible.md"


def _content() -> str:
    assert DOC_PATH.exists(), f"Missing Sports Stats Bible document: {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


class TestSportsStatsBibleDoc:
    def test_required_sections_are_present(self) -> None:
        content = _content()
        required_sections = [
            "# Sports Stats Bible",
            "## Purpose",
            "## Current architecture reality",
            "## Outlier-style target product",
            "## Source tiers",
            "## Basketball source matrix",
            "## Soccer source matrix",
            "## Baseball source matrix",
            "## Betting and props source matrix",
            "## Field dictionary",
            "## LLM grounding recipes",
            "## Implementation roadmap",
        ]
        for section in required_sections:
            assert section in content, f"Missing section: {section}"

    def test_mentions_required_sources(self) -> None:
        content = _content().lower()
        required_sources = [
            "outlier",
            "balldontlie",
            "nba.com",
            "nba_api",
            "espn",
            "statmuse",
            "basketball-reference",
            "livesport",
            "fbref",
            "fotmob",
            "whoscored",
            "football-data.org",
            "statsbomb",
            "prizepicks",
            "reddit",
            "mlb statsapi",
            "sofascore",
            "transfermarkt",
            "flashscore",
            "theoddsapi",
        ]
        for source in required_sources:
            assert source in content, f"Missing source: {source}"

    def test_enforces_free_only_constraint(self) -> None:
        content = _content().lower()
        assert "no paid subscriptions" in content
        assert "free-tier" in content or "free tier" in content

    def test_separates_direct_adapters_from_grounding_sources(self) -> None:
        content = _content().lower()
        assert "direct adapter" in content
        assert "llm grounding" in content
        assert "never make scrape-only public pages the only production dependency" in content

    def test_includes_outlier_roadmap_features(self) -> None:
        content = _content().lower()
        for feature in (
            "player trend cards",
            "injury context",
            "line movement",
            "odds comparison",
            "ev+",
            "arbitrage",
            "alerts",
            "responsible gaming",
        ):
            assert feature in content, f"Missing Outlier-style feature: {feature}"

    def test_documents_current_architecture(self) -> None:
        content = _content().lower()
        assert "gemini" in content
        assert "deterministic" in content
        assert "prizepicks" in content
