"""Tests for bible-style enrichment prompt variant."""

from __future__ import annotations

from bible_style_enrichment import BibleStyleEnrichmentProvider
from missing_input_enrichment import GeminiMissingInputEnrichmentProvider


class TestBibleStyleSystemPrompt:
    def test_contains_statmuse_url(self):
        prompt = BibleStyleEnrichmentProvider._build_system_prompt(sport="basketball")
        assert "statmuse.com/nba/ask" in prompt

    def test_contains_espn_gamelog_url(self):
        prompt = BibleStyleEnrichmentProvider._build_system_prompt(sport="basketball")
        assert "espn.com/nba/player/gamelog" in prompt

    def test_contains_nba_com_url(self):
        prompt = BibleStyleEnrichmentProvider._build_system_prompt(sport="basketball")
        assert "nba.com/stats/player" in prompt

    def test_contains_basketball_reference_url(self):
        prompt = BibleStyleEnrichmentProvider._build_system_prompt(sport="basketball")
        assert "basketball-reference.com/players" in prompt

    def test_contains_anti_pattern_null_rule(self):
        prompt = BibleStyleEnrichmentProvider._build_system_prompt(sport="basketball")
        assert "null rather than guessing" in prompt

    def test_contains_anti_pattern_single_source_rule(self):
        prompt = BibleStyleEnrichmentProvider._build_system_prompt(sport="basketball")
        assert "one source" in prompt.lower()

    def test_contains_recency_rule(self):
        prompt = BibleStyleEnrichmentProvider._build_system_prompt(sport="basketball")
        assert "most recent" in prompt.lower()

    def test_contains_required_fields(self):
        prompt = BibleStyleEnrichmentProvider._build_system_prompt(sport="basketball")
        assert "minutes_proj" in prompt
        assert "usage_rate" in prompt
        assert "points_last5" in prompt

    def test_generic_sport_has_base_only(self):
        prompt = BibleStyleEnrichmentProvider._build_system_prompt(sport="generic")
        assert "statmuse" not in prompt.lower()
        assert "Return exactly one JSON object" in prompt

    def test_base_prompt_preserved(self):
        prompt = BibleStyleEnrichmentProvider._build_system_prompt(sport="basketball")
        assert "search-grounded" in prompt
        assert "Never invent betting prop lines" in prompt

    def test_subclasses_production_provider(self):
        assert issubclass(BibleStyleEnrichmentProvider, GeminiMissingInputEnrichmentProvider)

    def test_overrides_build_system_prompt(self):
        bible_prompt = BibleStyleEnrichmentProvider._build_system_prompt(sport="basketball")
        prod_prompt = GeminiMissingInputEnrichmentProvider._build_system_prompt(sport="basketball")
        assert bible_prompt != prod_prompt
        assert len(bible_prompt) > len(prod_prompt)
