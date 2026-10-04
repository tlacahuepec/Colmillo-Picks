"""Sport-aware pick request model, validation, and legacy adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from nfl_domain import NFL_MARKETS


SUPPORTED_SPORTS: set[str] = {"soccer", "basketball", "baseball", "nfl"}

SPORT_MARKETS: dict[str, set[str]] = {
    "nfl": set(NFL_MARKETS),
    "soccer": {"passes", "shots"},
    "basketball": {
        "points", "rebounds", "assists", "threes",
        "steals", "blocks", "turnovers", "fantasy_score",
        "rebs_asts", "pra", "blks_stls",
        "fg_attempted", "fg_made", "two_pt_made",
    },
    "baseball": {"hits", "total_bases", "runs", "rbi", "home_runs", "strikeouts", "walks", "pitcher_outs"},
}

SPORT_LEAGUES: dict[str, set[str]] = {
    "nfl": {"nfl"},
    "soccer": {"premier_league", "la_liga", "serie_a", "bundesliga", "ligue_1", "mls", "champions_league"},
    "basketball": {"nba", "euroleague", "ncaab"},
    "baseball": {"mlb"},
}

LEAGUE_ALIASES: dict[str, dict[str, str]] = {
    "soccer": {
        # Premier League
        "premier_league": "premier_league",
        "premierleague": "premier_league",
        "premier": "premier_league",
        "epl": "premier_league",
        "english_premier_league": "premier_league",
        "englishpremierleague": "premier_league",
        "england_premier_league": "premier_league",
        "englandpremierleague": "premier_league",
        "barclays_premier_league": "premier_league",
        # La Liga
        "la_liga": "la_liga",
        "laliga": "la_liga",
        "spanish_la_liga": "la_liga",
        "spanishlaliga": "la_liga",
        "spain_la_liga": "la_liga",
        "spainlaliga": "la_liga",
        "primera_division": "la_liga",
        "primeradivision": "la_liga",
        "spain_primera_division": "la_liga",
        "spainprimeradivision": "la_liga",
        "la_liga_ea_sports": "la_liga",
        "laligaeasports": "la_liga",
        "la_liga_santander": "la_liga",
        "laligasantander": "la_liga",
        # Bundesliga
        "bundesliga": "bundesliga",
        "german_bundesliga": "bundesliga",
        "germanbundesliga": "bundesliga",
        "germany_bundesliga": "bundesliga",
        "germanybundesliga": "bundesliga",
        "bundesliga_1": "bundesliga",
        "1_bundesliga": "bundesliga",
        "1bundesliga": "bundesliga",
        "anothergerman_bundesliga": "bundesliga",
        "anothergermanbundesliga": "bundesliga",
        # Serie A
        "serie_a": "serie_a",
        "seriea": "serie_a",
        "italian_serie_a": "serie_a",
        "italianseriea": "serie_a",
        "italy_serie_a": "serie_a",
        "italyseriea": "serie_a",
        "serie_a_tim": "serie_a",
        "serie_a_enilive": "serie_a",
        "serieaenilive": "serie_a",
        # Ligue 1
        "ligue_1": "ligue_1",
        "ligue1": "ligue_1",
        "french_ligue_1": "ligue_1",
        "frenchligue1": "ligue_1",
        "france_ligue_1": "ligue_1",
        "franceligue1": "ligue_1",
        "ligue_1_uber_eats": "ligue_1",
        "ligue_1_mcdonalds": "ligue_1",
        "ligue1mcdonalds": "ligue_1",
        # Champions League
        "champions_league": "champions_league",
        "championsleague": "champions_league",
        "uefa_champions_league": "champions_league",
        "uefachampionsleague": "champions_league",
        "ucl": "champions_league",
        # MLS
        "mls": "mls",
        "major_league_soccer": "mls",
        "majorleaguesoccer": "mls",
        "usa_mls": "mls",
    },
    "basketball": {
        "nba": "nba",
        "national_basketball_association": "nba",
        "nationalbasketballassociation": "nba",
        "euroleague": "euroleague",
        "euro_league": "euroleague",
        "turkish_airlines_euroleague": "euroleague",
        "ncaab": "ncaab",
        "ncaa": "ncaab",
        "ncaa_basketball": "ncaab",
        "ncaabasketball": "ncaab",
        "college_basketball": "ncaab",
        "collegebasketball": "ncaab",
    },
    "baseball": {
        "mlb": "mlb",
        "major_league_baseball": "mlb",
        "majorleaguebaseball": "mlb",
    },
    "nfl": {
        "nfl": "nfl",
        "national_football_league": "nfl",
        "nationalfootballleague": "nfl",
    },
}

SUPPORTED_PLATFORMS: set[str] = {"prizepicks", "underdog", "draftkings"}


def normalize_league(league: str | None, sport: str | None = None) -> str | None:
    """Normalize a league name or alias into its canonical key."""
    if not league:
        return None
    raw = str(league).strip().lower()
    if not raw:
        return None

    import re

    normalized_key = re.sub(r"[\s\-_.]+", "_", raw).strip("_")
    alphanumeric_key = re.sub(r"[^a-z0-9]", "", raw)

    sports_to_search: list[str] = []
    if sport:
        cleaned_sport = sport.strip().lower()
        if cleaned_sport in LEAGUE_ALIASES:
            sports_to_search.append(cleaned_sport)
    if not sports_to_search:
        sports_to_search = list(LEAGUE_ALIASES.keys())

    for sp in sports_to_search:
        aliases = LEAGUE_ALIASES.get(sp, {})
        if normalized_key in aliases:
            return aliases[normalized_key]
        if alphanumeric_key in aliases:
            return aliases[alphanumeric_key]
        canonical = SPORT_LEAGUES.get(sp, set())
        if normalized_key in canonical:
            return normalized_key
        if alphanumeric_key in canonical:
            return alphanumeric_key

    return None


@dataclass(frozen=True)
class PickRequest:
    sport: str
    event_date: str
    home_team: str
    away_team: str
    markets: tuple[str, ...]
    top_n: int = 5
    league: str | None = None
    platform: str | None = None
    use_llm: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None

    def __post_init__(self) -> None:
        normalized_sport = self.sport.strip().lower() if self.sport else self.sport
        if normalized_sport != self.sport:
            object.__setattr__(self, "sport", normalized_sport)
        if self.league is not None:
            normalized = normalize_league(self.league, self.sport)
            if normalized is not None:
                object.__setattr__(self, "league", normalized)
            else:
                object.__setattr__(self, "league", self.league.strip().lower())


class PickRequestValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Invalid pick request: {'; '.join(errors)}")


def validate_pick_request(request: PickRequest) -> None:
    errors: list[str] = []

    if request.sport not in SUPPORTED_SPORTS:
        errors.append(
            f"Unsupported sport '{request.sport}'. Supported: {sorted(SUPPORTED_SPORTS)}"
        )
    else:
        valid_markets = SPORT_MARKETS.get(request.sport, set())
        for market in request.markets:
            if market not in valid_markets:
                errors.append(
                    f"Unsupported market '{market}' for sport '{request.sport}'. "
                    f"Valid: {sorted(valid_markets)}"
                )

        if request.league is not None:
            sport_leagues = SPORT_LEAGUES.get(request.sport, set())
            effective_league = normalize_league(request.league, request.sport) or request.league.lower()
            if effective_league not in sport_leagues:
                errors.append(
                    f"Unsupported league '{request.league}' for sport '{request.sport}'. "
                    f"Valid: {sorted(sport_leagues)}"
                )

    if request.platform is not None and request.platform.lower() not in SUPPORTED_PLATFORMS:
        errors.append(
            f"Unsupported platform '{request.platform}'. Supported: {sorted(SUPPORTED_PLATFORMS)}"
        )

    try:
        datetime.strptime(request.event_date, "%Y-%m-%d")
    except ValueError:
        errors.append(
            f"Invalid event_date '{request.event_date}'. Expected YYYY-MM-DD format."
        )

    if not (1 <= request.top_n <= 10):
        errors.append(f"top_n must be between 1 and 10, got {request.top_n}.")

    if errors:
        raise PickRequestValidationError(errors)


def pick_request_from_legacy_dict(request_dict: dict[str, Any]) -> PickRequest:
    from run_match_pick_pipeline import parse_match_query

    parsed = parse_match_query(request_dict["match_query"])

    return PickRequest(
        sport="soccer",
        event_date=parsed.match_date,
        home_team=parsed.home_team,
        away_team=parsed.away_team,
        markets=("passes", "shots"),
        top_n=int(request_dict.get("top_n", 5)),
        league=request_dict.get("competition"),
        use_llm=bool(request_dict.get("use_llm", False)),
        llm_provider=request_dict.get("llm_provider"),
        llm_model=request_dict.get("llm_model"),
    )


def pick_request_to_legacy_dict(request: PickRequest) -> dict[str, Any]:
    match_query = f"{request.home_team} - {request.away_team} {request.event_date}"
    return {
        "match_query": match_query,
        "top_n": request.top_n,
        "use_llm": request.use_llm,
        "llm_provider": request.llm_provider,
        "llm_model": request.llm_model,
        "competition": request.league or "League",
    }
