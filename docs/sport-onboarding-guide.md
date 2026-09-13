# Sport Onboarding Guide

How to add a new sport (e.g., NFL, NHL) to Colmillo-Picks.

With the config registry pattern, onboarding a sport is primarily configuration — no prompt builder or pipeline edits needed.

## Prerequisites

- Familiarity with the `SportModule` protocol (`skills/soccer-prop-picks/scripts/sport_module.py`)
- Familiarity with `SportEnrichmentConfig` (`skills/soccer-prop-picks/scripts/sport_enrichment_config.py`)
- Source research documented in `docs/sports-stats-bible.md`

## Steps

### 1. Define markets and required fields

Decide which betting markets your sport will support and what statistical fields the scoring engine needs per market.

Example for NFL:

```python
supported_markets = {"passing_yards", "rushing_yards", "receptions", "touchdowns"}

required_fields_per_market = {
    "passing_yards": ("pass_attempts_avg", "pass_yards_avg", "pass_yards_last5", "completion_pct"),
    "rushing_yards": ("rush_attempts_avg", "rush_yards_avg", "rush_yards_last5"),
    "receptions": ("targets_avg", "receptions_avg", "receptions_last5", "route_participation"),
    "touchdowns": ("td_avg", "td_last5", "red_zone_targets"),
}
```

### 2. Create a `SportEnrichmentConfig`

Add a frozen config instance in `skills/soccer-prop-picks/scripts/sport_enrichment_config.py`.

The config has five parts:

| Field | Purpose |
|-------|---------|
| `sport_id` | Matches `SportModule.sport_id` |
| `system_prompt_guidance` | LLM prompt text: field definitions, source URLs, quality rules |
| `required_fields_per_market` | Dict mapping market name to required field tuple |
| `field_format_rules` | Tuple of formatting constraints (e.g., "rate as decimal not percentage") |
| `preferred_sources` | Tuple of URL templates for LLM grounding |

Example skeleton for NFL:

```python
NFL_ENRICHMENT_CONFIG = SportEnrichmentConfig(
    sport_id="nfl",
    system_prompt_guidance=(
        "NFL-SPECIFIC GUIDANCE:\n"
        "The scoring engine requires these fields per player per market:\n"
        "- passing_yards: pass_attempts_avg, pass_yards_avg, pass_yards_last5, completion_pct\n"
        "- rushing_yards: rush_attempts_avg, rush_yards_avg, rush_yards_last5\n"
        "- receptions: targets_avg, receptions_avg, receptions_last5, route_participation\n"
        "- touchdowns: td_avg, td_last5, red_zone_targets\n\n"
        "PREFERRED SOURCES (search these first, in priority order):\n"
        "1. ESPN (https://www.espn.com/nfl/player/gamelog/_/id/{espn_id}/{player-slug})\n"
        "2. PFF (https://www.pff.com/nfl/players/{player-slug}/{pff_id})\n"
        "3. NFL.com (https://www.nfl.com/players/{player-slug}/stats/)\n"
        "4. FantasyPros (https://www.fantasypros.com/nfl/players/{player-slug}.php)\n\n"
        "QUALITY RULES:\n"
        "- Account for bye weeks when computing last5 (skip bye, use 5 actual games).\n"
        "- Note opponent defensive rank for the upcoming matchup.\n"
        "- Return null rather than guessing when no source can verify the value.\n\n"
        "Return numeric values (not strings). Use null ONLY when no source can verify the value."
    ),
    required_fields_per_market={
        "passing_yards": ("pass_attempts_avg", "pass_yards_avg", "pass_yards_last5", "completion_pct"),
        "rushing_yards": ("rush_attempts_avg", "rush_yards_avg", "rush_yards_last5"),
        "receptions": ("targets_avg", "receptions_avg", "receptions_last5", "route_participation"),
        "touchdowns": ("td_avg", "td_last5", "red_zone_targets"),
    },
    field_format_rules=(
        "completion_pct must be expressed as a decimal (e.g., 0.67), not a percentage.",
        "route_participation must be expressed as a decimal (e.g., 0.85), not a percentage.",
        "last5 averages should skip bye weeks — use 5 most recent games actually played.",
    ),
    preferred_sources=(
        "https://www.espn.com/nfl/player/gamelog/_/id/{espn_id}/{player-slug}",
        "https://www.pff.com/nfl/players/{player-slug}/{pff_id}",
        "https://www.nfl.com/players/{player-slug}/stats/",
        "https://www.fantasypros.com/nfl/players/{player-slug}.php",
    ),
)
```

### 3. Register the config

In `_build_default_registry()` within `sport_enrichment_config.py`:

```python
def _build_default_registry() -> SportEnrichmentConfigRegistry:
    registry = SportEnrichmentConfigRegistry()
    registry.register(BASKETBALL_ENRICHMENT_CONFIG)
    registry.register(BASEBALL_ENRICHMENT_CONFIG)
    registry.register(SOCCER_ENRICHMENT_CONFIG)
    registry.register(NFL_ENRICHMENT_CONFIG)  # <-- add here
    return registry
```

This is all that's needed for enrichment — `_build_system_prompt(sport="nfl")` will automatically pick up the config via `get_enrichment_config("nfl")`.

### 4. Create a `SportModule` implementation

Implement the `SportModule` protocol in a new file (e.g., `nfl_module.py`) or add to `sport_module.py`:

```python
class NflModule:
    @property
    def sport_id(self) -> str:
        return "nfl"

    @property
    def supported_leagues(self) -> set[str]:
        return {"NFL"}

    @property
    def supported_markets(self) -> set[str]:
        return {"passing_yards", "rushing_yards", "receptions", "touchdowns"}

    def collect_inputs(self, *, home_team: str, away_team: str, match_date: str, league: str | None = None) -> dict[str, Any]:
        # Build dependency bundle and collect match data
        ...

    def score(self, match_inputs: dict[str, Any], *, markets: tuple[str, ...] = ()) -> list[dict[str, Any]]:
        # Score player props using collected inputs
        ...

    def explain(self, scored_pick: dict[str, Any]) -> str:
        # Human-readable explanation of a scored pick
        ...
```

Register it in `_build_default_registry()` in `sport_module.py`:

```python
def _build_default_registry() -> SportModuleRegistry:
    registry = SportModuleRegistry()
    registry.register(SoccerModule())
    registry.register(_build_basketball_module())
    registry.register(_build_baseball_module())
    registry.register(NflModule())  # <-- add here
    return registry
```

### 5. Add tests

Two test classes minimum:

**A) Config tests** in `tests/test_sport_enrichment_config.py`:

```python
class TestNflConfig:
    def test_nfl_config_exists(self):
        config = get_enrichment_config("nfl")
        assert config is not None
        assert config.sport_id == "nfl"

    def test_nfl_has_required_fields_for_all_markets(self):
        config = get_enrichment_config("nfl")
        assert "passing_yards" in config.required_fields_per_market
        assert "rushing_yards" in config.required_fields_per_market
        assert "receptions" in config.required_fields_per_market
        assert "touchdowns" in config.required_fields_per_market

    def test_nfl_has_preferred_sources(self):
        config = get_enrichment_config("nfl")
        sources_text = " ".join(config.preferred_sources)
        assert "espn.com" in sources_text
        assert "nfl.com" in sources_text
```

**B) Bible integration tests** verifying URLs and anti-patterns appear in the prompt:

```python
class TestNflBibleIntegration:
    def test_contains_espn_url(self):
        config = get_enrichment_config("nfl")
        assert "espn.com/nfl/player/gamelog" in config.system_prompt_guidance

    def test_contains_null_over_guessing_rule(self):
        config = get_enrichment_config("nfl")
        assert "null" in config.system_prompt_guidance.lower()
```

### 6. Update the Sports Stats Bible

Add entries to `docs/sports-stats-bible.md`:

1. **Source matrix** — table of sources with data fields, free API status, LLM grounding candidacy
2. **Grounding recipe** — preferred source order + prompt rules
3. **Anti-patterns** — sport-specific rules (add to the existing anti-patterns section)

## Checklist

- [ ] Markets and required fields defined
- [ ] `SportEnrichmentConfig` created with guidance, URLs, rules
- [ ] Config registered in `_build_default_registry()`
- [ ] `SportModule` protocol implemented
- [ ] Module registered in `SportModuleRegistry`
- [ ] Tests: config exists, fields present, URLs in prompt
- [ ] Bible updated: source matrix, recipe, anti-patterns
- [ ] `ruff check` passes
- [ ] All existing tests still pass

## Reference implementations

| Sport | Config | Module | Tests |
|-------|--------|--------|-------|
| Basketball | `BASKETBALL_ENRICHMENT_CONFIG` | `_build_basketball_module()` | `TestBasketballBibleIntegration` |
| Soccer | `SOCCER_ENRICHMENT_CONFIG` | `SoccerModule` | `TestSoccerBibleIntegration` |
| Baseball | `BASEBALL_ENRICHMENT_CONFIG` | `_build_baseball_module()` | `TestBaseballFieldScoring` |
