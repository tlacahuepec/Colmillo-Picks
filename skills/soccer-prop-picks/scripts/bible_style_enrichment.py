"""Bible-style enrichment provider with explicit source URLs and anti-patterns.

Subclasses the production provider to override only the system prompt,
keeping all other enrichment logic (parsing, best-of-N, provenance) intact.
Used for A/B testing prompt quality (Story #272) without modifying production code.
"""

from __future__ import annotations

from missing_input_enrichment import GeminiMissingInputEnrichmentProvider


class BibleStyleEnrichmentProvider(GeminiMissingInputEnrichmentProvider):
    """Enrichment provider using bible-guided prompts with explicit URLs."""

    @staticmethod
    def _build_system_prompt(*, sport: str = "generic") -> str:
        base = (
            "You enrich missing sports betting-analysis inputs after official providers were tried first. "
            "Return exactly one JSON object. Use search-grounded, source-labeled data only. "
            "Never invent betting prop lines; include line source metadata for each line or leave it unknown. "
            "Use null for unverified values. Do not include markdown or prose."
        )
        if sport == "basketball":
            base += (
                "\n\nBASKETBALL-SPECIFIC GUIDANCE:\n"
                "The scoring engine requires these exact numeric fields per player:\n"
                "- minutes_proj: Projected minutes for this game (typically 20-38 for starters)\n"
                "- usage_rate: Fraction of team possessions used while on court (decimal 0.15-0.35, NOT percentage)\n"
                "- points_avg / points_last5: Season and last-5-game scoring averages\n"
                "- rebound_avg / rebound_last5: Season and last-5-game rebounding averages\n"
                "- assist_avg / assist_last5: Season and last-5-game assist averages\n"
                "- threes_avg / threes_last5: Season and last-5-game three-pointers made averages\n"
                "- three_point_attempts: Season average 3PA per game\n\n"
                "PREFERRED SOURCES (search these first, in priority order):\n"
                "1. StatMuse (https://www.statmuse.com/nba/ask/{player-slug}-last-5-games) — best for last-N game summaries\n"
                "2. ESPN gamelog (https://www.espn.com/nba/player/gamelog/_/id/{espn-id}/{player-slug}) — per-game stats rows\n"
                "3. NBA.com stats (https://www.nba.com/stats/player/{nba-id}) — official splits, usage, advanced\n"
                "4. Basketball-Reference (https://www.basketball-reference.com/players/{letter}/{bbref-id}.html) — season/career/game logs\n\n"
                "ANTI-PATTERN RULES:\n"
                "- Never accept a critical numeric from only one source without noting lower confidence.\n"
                "- Prefer the most recent settled games for last5 fields. Note game dates.\n"
                "- Note back-to-back or rest days when relevant to minutes projection.\n"
                "- Return null rather than guessing or averaging creatively.\n\n"
                "Return numeric values (not strings). Use null ONLY when no source can verify the value."
            )
        return base
