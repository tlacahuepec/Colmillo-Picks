"""Sport-agnostic enrichment config dataclass and registry.

Each sport defines its enrichment configuration — system prompt guidance,
required fields per market, field format rules, and preferred sources.
Adding a new sport requires only creating a new config instance and
registering it; no prompt builder edits needed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SportEnrichmentConfig:
    sport_id: str
    system_prompt_guidance: str
    required_fields_per_market: dict[str, tuple[str, ...]]
    field_format_rules: tuple[str, ...]
    preferred_sources: tuple[str, ...]


class SportEnrichmentConfigRegistry:
    def __init__(self) -> None:
        self._configs: dict[str, SportEnrichmentConfig] = {}

    def register(self, config: SportEnrichmentConfig) -> None:
        self._configs[config.sport_id] = config

    def get(self, sport_id: str) -> SportEnrichmentConfig | None:
        return self._configs.get(sport_id)

    @property
    def registered_sports(self) -> set[str]:
        return set(self._configs.keys())


BASKETBALL_ENRICHMENT_CONFIG = SportEnrichmentConfig(
    sport_id="basketball",
    system_prompt_guidance=(
        "BASKETBALL-SPECIFIC GUIDANCE:\n"
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
        "QUALITY RULES:\n"
        "- Prefer the most recent settled games for last5 fields.\n"
        "- Note back-to-back or rest days when relevant to minutes projection.\n"
        "- Return null rather than guessing when no source can verify the value.\n\n"
        "Return numeric values (not strings). Use null ONLY when no source can verify the value."
    ),
    required_fields_per_market={
        "points": ("minutes_proj", "usage_rate", "points_avg", "points_last5"),
        "rebounds": ("minutes_proj", "usage_rate", "rebound_avg", "rebound_last5"),
        "assists": ("minutes_proj", "usage_rate", "assist_avg", "assist_last5"),
        "threes": ("minutes_proj", "usage_rate", "threes_avg", "threes_last5", "three_point_attempts"),
    },
    field_format_rules=(
        "usage_rate must be expressed as a decimal (e.g., 0.28), not a percentage (e.g., 28).",
        "minutes_proj should reflect current rotation status and recent minutes pattern.",
        "last5 averages should be from the 5 most recent games actually played.",
    ),
    preferred_sources=(
        "https://www.statmuse.com/nba/ask/{player-slug}-last-5-games",
        "https://www.espn.com/nba/player/gamelog/_/id/{espn-id}/{player-slug}",
        "https://www.nba.com/stats/player/{nba-id}",
        "https://www.basketball-reference.com/players/{letter}/{bbref-id}.html",
    ),
)

BASEBALL_ENRICHMENT_CONFIG = SportEnrichmentConfig(
    sport_id="baseball",
    system_prompt_guidance="",
    required_fields_per_market={
        "hits": ("batting_avg", "hits_last5", "at_bats_avg"),
        "total_bases": ("batting_avg", "slugging_pct", "total_bases_last5"),
        "runs": ("batting_avg", "runs_last5", "obp"),
        "rbi": ("batting_avg", "rbi_last5", "runners_in_scoring_position_avg"),
        "strikeouts": ("k_rate", "strikeouts_last5", "pitcher_k_rate"),
        "home_runs": ("batting_avg", "slugging_pct", "home_runs_last5"),
        "walks": ("obp", "walks_last5", "pitcher_walk_rate"),
        "pitcher_outs": ("pitcher_outs_avg", "pitcher_outs_last5", "pitch_count_avg"),
    },
    field_format_rules=(),
    preferred_sources=("baseball-reference.com", "fangraphs.com"),
)

SOCCER_ENRICHMENT_CONFIG = SportEnrichmentConfig(
    sport_id="soccer",
    system_prompt_guidance=(
        "SOCCER-SPECIFIC GUIDANCE:\n"
        "The scoring engine requires these fields per player per market:\n"
        "- goals: minutes, starts, xG, goals_last5, opponent_defense_rank\n"
        "- assists: minutes, starts, xA, assists_last5, key_passes\n"
        "- shots: minutes, starts, shots_last5, shots_on_target_last5\n"
        "- passes: minutes, starts, passes_last5, pass_completion\n\n"
        "PREFERRED SOURCES (search these first, in priority order):\n"
        "1. FotMob (https://www.fotmob.com/players/{fotmob_id}/{player-slug}) — player profiles, recent form, goals, assists, xG/xA\n"
        "2. Sofascore (https://www.sofascore.com/player/{player-slug}/{sofascore_id}) — player ratings, match events, lineups\n"
        "3. Transfermarkt (https://www.transfermarkt.com/{player-slug}/profil/spieler/{tm_id}) — injuries, transfers, squad availability\n"
        "4. FBref (https://fbref.com/en/players/{fbref_id}/{player}) — advanced stats, xG, progressive carries\n"
        "5. ESPN (https://www.espn.com/soccer/player/_/id/{espn_id}/{player-slug}) — profile, appearances, game logs\n\n"
        "QUALITY RULES:\n"
        "- Never blend club and national-team form unless the market explicitly requires it.\n"
        "- Always preserve league/competition and date context.\n"
        "- Cross-check injuries from 2+ sources (Transfermarkt + Sofascore or ESPN).\n"
        "- Prefer FotMob and Sofascore for recent player form; Transfermarkt for injury/availability.\n"
        "- Return null rather than guessing when no source can verify the value.\n\n"
        "Return numeric values (not strings). Use null ONLY when no source can verify the value."
    ),
    required_fields_per_market={
        "goals": ("minutes", "starts", "xG", "goals_last5", "opponent_defense_rank"),
        "assists": ("minutes", "starts", "xA", "assists_last5", "key_passes"),
        "shots": ("minutes", "starts", "shots_last5", "shots_on_target_last5"),
        "passes": ("minutes", "starts", "passes_last5", "pass_completion"),
    },
    field_format_rules=(
        "xG and xA must be expressed as decimals per 90 minutes (e.g., 0.45), not totals.",
        "pass_completion must be expressed as a decimal (e.g., 0.82), not a percentage.",
        "last5 averages should be from the 5 most recent club matches actually played.",
    ),
    preferred_sources=(
        "https://www.fotmob.com/players/{fotmob_id}/{player-slug}",
        "https://www.sofascore.com/player/{player-slug}/{sofascore_id}",
        "https://www.transfermarkt.com/{player-slug}/profil/spieler/{tm_id}",
        "https://fbref.com/en/players/{fbref_id}/{player}",
        "https://www.espn.com/soccer/player/_/id/{espn_id}/{player-slug}",
    ),
)


NFL_ENRICHMENT_CONFIG = SportEnrichmentConfig(
    sport_id="nfl",
    system_prompt_guidance=(
        "NFL-SPECIFIC GUIDANCE: Use https://www.nfl.com/stats/player-stats/, "
        "https://www.nfl.com/injuries/, https://www.nfl.com/schedules/ and ESPN NFL game logs. "
        "Confirm current roster, starting quarterback and injury status for this fixture. "
        "Use only regular season and postseason games; exclude preseason. "
        "Skip bye weeks and DNPs; use five actual completed games, with date and season on each. "
        "Never replace a missing early-season sample with invented averages. "
        "scorer_touchdowns means touchdowns scored by the player, including rushing/receiving/returns; "
        "passing touchdowns do not count. interceptions_thrown means QB interceptions, not defensive interceptions. "
        "opportunity_ratio = recent attempts/targets per game divided by season attempts/targets per game. "
        "opponent_factor = opponent allowed production divided by league average (1.0 is neutral). "
        "Return these ratios only when verified; otherwise null. "
        "Team averages and last5 must be from completed games before the requested fixture. "
        "If a team has not played in the current season, use its most recent completed season "
        "and set the team season field to that historical year, never the upcoming season. "
        "For team last5, compute points scored and allowed from the five actual most recent "
        "regular/postseason final scores. For players, include per-game numeric stats, not just a roster. "
        "Use exact provider search citation URLs. Never fabricate odds, source URLs or timestamps. "
        "Return null rather than guessing when a source cannot verify a value."
    ),
    required_fields_per_market={
        market: ("game_logs", "injury_status", "source_urls")
        for market in ("passing_yards", "passing_touchdowns", "interceptions_thrown",
                       "rushing_yards", "receiving_yards", "receptions", "anytime_touchdown")
    } | {market: ("points_for_avg", "points_against_avg", "points_for_last5", "points_against_last5")
         for market in ("moneyline", "spread", "total")},
    field_format_rules=("Odds must be decimal, greater than 1.", "Ratios are decimals, not percentages.",
                        "Use five games actually played, skipping byes and preseason."),
    preferred_sources=("https://www.nfl.com/stats/player-stats/", "https://www.nfl.com/injuries/",
                       "https://www.nfl.com/schedules/", "https://www.espn.com/nfl/"),
)


def _build_default_registry() -> SportEnrichmentConfigRegistry:
    registry = SportEnrichmentConfigRegistry()
    registry.register(BASKETBALL_ENRICHMENT_CONFIG)
    registry.register(BASEBALL_ENRICHMENT_CONFIG)
    registry.register(SOCCER_ENRICHMENT_CONFIG)
    registry.register(NFL_ENRICHMENT_CONFIG)
    return registry


_DEFAULT_REGISTRY: SportEnrichmentConfigRegistry | None = None


def get_enrichment_config(sport_id: str) -> SportEnrichmentConfig | None:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = _build_default_registry()
    return _DEFAULT_REGISTRY.get(sport_id)
