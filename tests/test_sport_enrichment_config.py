"""Tests for sport enrichment config dataclass and registry."""

from __future__ import annotations

import pytest

from sport_enrichment_config import (
    SportEnrichmentConfig,
    SportEnrichmentConfigRegistry,
    get_enrichment_config,
)


class TestSportEnrichmentConfig:
    def test_create_basketball_config(self):
        config = SportEnrichmentConfig(
            sport_id="basketball",
            system_prompt_guidance="BASKETBALL-SPECIFIC GUIDANCE",
            required_fields_per_market={
                "points": ("minutes_proj", "usage_rate", "points_avg", "points_last5"),
            },
            field_format_rules=(
                "usage_rate must be expressed as a decimal (e.g., 0.28), not a percentage.",
            ),
            preferred_sources=("basketball-reference.com", "nba.com/stats"),
        )
        assert config.sport_id == "basketball"
        assert "minutes_proj" in config.required_fields_per_market["points"]

    def test_config_is_frozen(self):
        config = SportEnrichmentConfig(
            sport_id="basketball",
            system_prompt_guidance="test",
            required_fields_per_market={},
            field_format_rules=(),
            preferred_sources=(),
        )
        with pytest.raises(Exception):
            config.sport_id = "soccer"


class TestSportEnrichmentConfigRegistry:
    def test_register_and_get(self):
        registry = SportEnrichmentConfigRegistry()
        config = SportEnrichmentConfig(
            sport_id="basketball",
            system_prompt_guidance="test guidance",
            required_fields_per_market={},
            field_format_rules=(),
            preferred_sources=(),
        )
        registry.register(config)
        assert registry.get("basketball") is config

    def test_get_unregistered_returns_none(self):
        registry = SportEnrichmentConfigRegistry()
        assert registry.get("unknown_sport") is None

    def test_register_multiple_sports(self):
        registry = SportEnrichmentConfigRegistry()
        basketball = SportEnrichmentConfig(
            sport_id="basketball",
            system_prompt_guidance="bball",
            required_fields_per_market={},
            field_format_rules=(),
            preferred_sources=(),
        )
        baseball = SportEnrichmentConfig(
            sport_id="baseball",
            system_prompt_guidance="",
            required_fields_per_market={},
            field_format_rules=(),
            preferred_sources=(),
        )
        registry.register(basketball)
        registry.register(baseball)
        assert registry.get("basketball") is basketball
        assert registry.get("baseball") is baseball

    def test_registered_sports_property(self):
        registry = SportEnrichmentConfigRegistry()
        config = SportEnrichmentConfig(
            sport_id="basketball",
            system_prompt_guidance="",
            required_fields_per_market={},
            field_format_rules=(),
            preferred_sources=(),
        )
        registry.register(config)
        assert "basketball" in registry.registered_sports


class TestDefaultConfigs:
    def test_basketball_config_exists(self):
        config = get_enrichment_config("basketball")
        assert config is not None
        assert config.sport_id == "basketball"

    def test_basketball_has_system_prompt_guidance(self):
        config = get_enrichment_config("basketball")
        assert "minutes_proj" in config.system_prompt_guidance
        assert "usage_rate" in config.system_prompt_guidance

    def test_basketball_has_required_fields(self):
        config = get_enrichment_config("basketball")
        assert "points" in config.required_fields_per_market
        assert "rebounds" in config.required_fields_per_market
        assert "assists" in config.required_fields_per_market
        assert "threes" in config.required_fields_per_market

    def test_basketball_has_field_format_rules(self):
        config = get_enrichment_config("basketball")
        assert len(config.field_format_rules) > 0
        assert any("usage_rate" in rule for rule in config.field_format_rules)

    def test_basketball_has_preferred_sources(self):
        config = get_enrichment_config("basketball")
        assert any("basketball-reference" in s for s in config.preferred_sources)

    def test_baseball_config_exists(self):
        config = get_enrichment_config("baseball")
        assert config is not None
        assert config.sport_id == "baseball"

    def test_unknown_sport_returns_none(self):
        config = get_enrichment_config("curling")
        assert config is None

    def test_generic_returns_none(self):
        config = get_enrichment_config("generic")
        assert config is None


class TestSoccerConfig:
    def test_soccer_config_exists(self):
        config = get_enrichment_config("soccer")
        assert config is not None
        assert config.sport_id == "soccer"

    def test_soccer_has_system_prompt_guidance(self):
        config = get_enrichment_config("soccer")
        assert config.system_prompt_guidance != ""

    def test_soccer_has_required_fields_for_all_markets(self):
        config = get_enrichment_config("soccer")
        assert "goals" in config.required_fields_per_market
        assert "assists" in config.required_fields_per_market
        assert "shots" in config.required_fields_per_market
        assert "passes" in config.required_fields_per_market

    def test_soccer_has_field_format_rules(self):
        config = get_enrichment_config("soccer")
        assert len(config.field_format_rules) > 0
        assert any("xG" in rule or "xA" in rule for rule in config.field_format_rules)

    def test_soccer_has_preferred_sources(self):
        config = get_enrichment_config("soccer")
        assert len(config.preferred_sources) == 5


class TestSoccerBibleIntegration:
    """Verify soccer config contains bible-sourced URLs and anti-patterns."""

    def test_contains_fotmob_url(self):
        config = get_enrichment_config("soccer")
        assert "fotmob.com/players" in config.system_prompt_guidance

    def test_contains_sofascore_url(self):
        config = get_enrichment_config("soccer")
        assert "sofascore.com/player" in config.system_prompt_guidance

    def test_contains_transfermarkt_url(self):
        config = get_enrichment_config("soccer")
        assert "transfermarkt.com" in config.system_prompt_guidance

    def test_contains_fbref_url(self):
        config = get_enrichment_config("soccer")
        assert "fbref.com/en/players" in config.system_prompt_guidance

    def test_contains_espn_url(self):
        config = get_enrichment_config("soccer")
        assert "espn.com/soccer/player" in config.system_prompt_guidance

    def test_contains_club_national_team_antipattern(self):
        config = get_enrichment_config("soccer")
        assert "national-team" in config.system_prompt_guidance.lower()

    def test_contains_injury_crosscheck_antipattern(self):
        config = get_enrichment_config("soccer")
        assert "2+" in config.system_prompt_guidance or "two" in config.system_prompt_guidance.lower()

    def test_contains_null_over_guessing_rule(self):
        config = get_enrichment_config("soccer")
        assert "null" in config.system_prompt_guidance.lower()

    def test_preferred_sources_include_bible_urls(self):
        config = get_enrichment_config("soccer")
        sources_text = " ".join(config.preferred_sources)
        assert "fotmob.com" in sources_text
        assert "sofascore.com" in sources_text
        assert "transfermarkt.com" in sources_text
        assert "fbref.com" in sources_text
        assert "espn.com" in sources_text


class TestBasketballBibleIntegration:
    """Verify basketball config contains bible-sourced URLs and anti-patterns."""

    def test_contains_statmuse_url(self):
        config = get_enrichment_config("basketball")
        assert "statmuse.com/nba/ask" in config.system_prompt_guidance

    def test_contains_espn_gamelog_url(self):
        config = get_enrichment_config("basketball")
        assert "espn.com/nba/player/gamelog" in config.system_prompt_guidance

    def test_contains_nba_com_url(self):
        config = get_enrichment_config("basketball")
        assert "nba.com/stats/player" in config.system_prompt_guidance

    def test_contains_basketball_reference_url(self):
        config = get_enrichment_config("basketball")
        assert "basketball-reference.com/players" in config.system_prompt_guidance

    def test_contains_null_over_guessing_rule(self):
        config = get_enrichment_config("basketball")
        assert "null" in config.system_prompt_guidance.lower()

    def test_contains_recency_preference(self):
        config = get_enrichment_config("basketball")
        assert "recent" in config.system_prompt_guidance.lower()

    def test_preferred_sources_include_bible_urls(self):
        config = get_enrichment_config("basketball")
        sources_text = " ".join(config.preferred_sources)
        assert "statmuse.com" in sources_text
        assert "espn.com" in sources_text
        assert "nba.com" in sources_text
        assert "basketball-reference.com" in sources_text
