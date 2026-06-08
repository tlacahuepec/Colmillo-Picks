"""Sport-aware pick request model, validation, and legacy adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


SUPPORTED_SPORTS: set[str] = {"soccer", "basketball", "baseball"}

SPORT_MARKETS: dict[str, set[str]] = {
    "soccer": {"passes", "shots"},
    "basketball": {"points", "rebounds", "assists", "threes"},
    "baseball": {"hits", "total_bases", "runs", "rbi", "home_runs", "strikeouts", "walks", "pitcher_outs"},
}

SPORT_LEAGUES: dict[str, set[str]] = {
    "soccer": {"premier_league", "la_liga", "serie_a", "bundesliga", "ligue_1", "mls", "champions_league"},
    "basketball": {"nba", "euroleague", "ncaab"},
    "baseball": {"mlb"},
}

SUPPORTED_PLATFORMS: set[str] = {"prizepicks", "underdog", "draftkings"}


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
            if request.league.lower() not in sport_leagues:
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
