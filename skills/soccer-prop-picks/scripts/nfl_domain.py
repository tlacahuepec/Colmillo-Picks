"""NFL market identities and validation shared by collection and presentation."""

from datetime import datetime, timedelta, timezone
from math import isfinite
from urllib.parse import urlparse

NFL_PLAYER_MARKETS = (
    "passing_yards",
    "passing_touchdowns",
    "interceptions_thrown",
    "rushing_yards",
    "receiving_yards",
    "receptions",
    "anytime_touchdown",
)
NFL_GAME_MARKETS = ("moneyline", "spread", "total")
NFL_MARKETS = NFL_PLAYER_MARKETS + NFL_GAME_MARKETS
NO_LINE_MARKETS = {"moneyline", "anytime_touchdown"}

_TEAM_NAMES = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}
_ALIASES = {
    alias.casefold(): name
    for code, name in _TEAM_NAMES.items()
    for alias in (code, name, name.split()[-1])
}
_ALIASES.update({"wsh": _TEAM_NAMES["WAS"], "jac": _TEAM_NAMES["JAX"]})


def resolve_team(value: str) -> str:
    return _ALIASES.get(value.strip().casefold(), value.strip())


def number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if isfinite(value) else None


def timestamp(value) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (TypeError, ValueError):
        return None


def web_url(value) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username


def valid_offer(offer: dict, *, now: datetime | None = None) -> bool:
    market = offer.get("market")
    if (
        market not in NFL_MARKETS
        or not offer.get("subject_name")
        or not offer.get("sportsbook")
    ):
        return False
    if offer.get("period") != "full_game" or offer.get("includes_overtime") is not True:
        return False
    if offer.get("is_live") is not False or offer.get("is_primary") is not True:
        return False
    odds = number(offer.get("odds_decimal"))
    observed = timestamp(offer.get("observed_at"))
    now = now or datetime.now(timezone.utc)
    if (
        odds is None
        or odds <= 1
        or not web_url(offer.get("source_url"))
        or observed is None
    ):
        return False
    if not now - timedelta(hours=24) <= observed <= now + timedelta(minutes=5):
        return False
    selection = offer.get("selection")
    if market in {"moneyline", "spread"}:
        valid_selection = selection in {"home", "away"}
    elif market == "anytime_touchdown":
        valid_selection = selection == "yes"
    else:
        valid_selection = selection in {"over", "under"}
    if not valid_selection:
        return False
    if market in NO_LINE_MARKETS:
        return offer.get("line") is None
    line = number(offer.get("line"))
    return line is not None and (market == "spread" or line >= 0)


def has_valid_pick_line(pick: dict) -> bool:
    """Preserve legacy behavior, with explicit rules for NFL offers."""
    if pick.get("sport") != "nfl":
        return bool(pick.get("line"))
    if pick.get("market") in NO_LINE_MARKETS:
        return pick.get("line") is None
    line = number(pick.get("line"))
    return line is not None and (pick.get("market") == "spread" or line >= 0)
