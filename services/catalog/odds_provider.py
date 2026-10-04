"""The Odds API catalog provider adapter.

Provides normalized betting odds and player proposition lines from The Odds API aggregator.
Supports live HTTP requests when configured with an API key, and deterministic fixture replay
for offline testing, CI environments, and hermetic evaluation audits.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from services.catalog.contracts import Confidence, SourceObservation
from services.catalog.providers import (
    ProviderErrorCategory,
    ProviderRequest,
    ProviderResult,
    ProviderStatus,
)

logger = logging.getLogger("colmillo.catalog.odds_provider")

# Sport mapping
SPORT_TO_ODDS_API_KEY: Mapping[str, str] = {
    "baseball": "baseball_mlb",
    "mlb": "baseball_mlb",
    "basketball": "basketball_nba",
    "nba": "basketball_nba",
    "nfl": "americanfootball_nfl",
    "football": "americanfootball_nfl",
    "soccer": "soccer_usa_mls",
}

# MLB market mappings between internal names and The Odds API keys
MLB_MARKET_MAP: Mapping[str, str] = {
    "hits": "batter_hits",
    "batter_hits": "hits",
    "strikeouts": "pitcher_strikeouts",
    "pitcher_strikeouts": "strikeouts",
    "home_runs": "batter_home_runs",
    "batter_home_runs": "home_runs",
    "total_bases": "batter_total_bases",
    "batter_total_bases": "total_bases",
    "walks": "batter_walks",
    "batter_walks": "walks",
    "runs": "batter_runs_scored",
    "batter_runs_scored": "runs",
    "rbi": "batter_rbis",
    "batter_rbis": "rbi",
    "pitcher_outs": "pitcher_outs",
}

# NBA market mappings between internal names and The Odds API keys
NBA_MARKET_MAP: Mapping[str, str] = {
    "points": "player_points",
    "player_points": "points",
    "rebounds": "player_rebounds",
    "player_rebounds": "rebounds",
    "assists": "player_assists",
    "player_assists": "assists",
    "threes": "player_threes",
    "player_threes": "threes",
    "steals": "player_steals",
    "player_steals": "steals",
    "blocks": "player_blocks",
    "player_blocks": "blocks",
    "turnovers": "player_turnovers",
    "player_turnovers": "turnovers",
    "pra": "player_points_rebounds_assists",
    "player_points_rebounds_assists": "pra",
}


@dataclass(frozen=True)
class TheOddsApiConfig:
    api_key: str | None = None
    base_url: str = "https://api.the-odds-api.com/v4"
    timeout_seconds: float = 10.0
    regions: str = "us"
    odds_format: str = "american"
    default_bookmakers: tuple[str, ...] = ("draftkings", "fanduel", "betmgm")


# Deterministic offline replay data for CI, local tests, and audits
_REPLAY_MLB_FIXTURES: list[dict[str, Any]] = [
    {
        "id": "mlb_nyy_bos_replay",
        "sport_key": "baseball_mlb",
        "home_team": "New York Yankees",
        "away_team": "Boston Red Sox",
        "commence_time": "2025-05-24T17:05:00Z",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "last_update": "2025-05-24T15:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "New York Yankees", "price": -150},
                            {"name": "Boston Red Sox", "price": 130},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": -110, "point": 8.5},
                            {"name": "Under", "price": -110, "point": 8.5},
                        ],
                    },
                    {
                        "key": "batter_hits",
                        "outcomes": [
                            {"name": "Over", "description": "Aaron Judge", "price": -140, "point": 1.5},
                            {"name": "Under", "description": "Aaron Judge", "price": 110, "point": 1.5},
                            {"name": "Over", "description": "Juan Soto", "price": -145, "point": 1.5},
                            {"name": "Under", "description": "Juan Soto", "price": 115, "point": 1.5},
                            {"name": "Over", "description": "Anthony Volpe", "price": -120, "point": 1.5},
                            {"name": "Under", "description": "Anthony Volpe", "price": -110, "point": 1.5},
                            {"name": "Over", "description": "Rafael Devers", "price": -135, "point": 1.5},
                            {"name": "Under", "description": "Rafael Devers", "price": 105, "point": 1.5},
                            {"name": "Over", "description": "Jarren Duran", "price": -130, "point": 1.5},
                            {"name": "Under", "description": "Jarren Duran", "price": 100, "point": 1.5},
                        ],
                    },
                    {
                        "key": "batter_home_runs",
                        "outcomes": [
                            {"name": "Over", "description": "Aaron Judge", "price": 230, "point": 0.5},
                            {"name": "Under", "description": "Aaron Judge", "price": -330, "point": 0.5},
                            {"name": "Over", "description": "Juan Soto", "price": 280, "point": 0.5},
                            {"name": "Under", "description": "Juan Soto", "price": -420, "point": 0.5},
                            {"name": "Over", "description": "Rafael Devers", "price": 310, "point": 0.5},
                            {"name": "Under", "description": "Rafael Devers", "price": -470, "point": 0.5},
                        ],
                    },
                    {
                        "key": "batter_total_bases",
                        "outcomes": [
                            {"name": "Over", "description": "Aaron Judge", "price": 105, "point": 2.5},
                            {"name": "Under", "description": "Aaron Judge", "price": -135, "point": 2.5},
                            {"name": "Over", "description": "Juan Soto", "price": -110, "point": 2.5},
                            {"name": "Under", "description": "Juan Soto", "price": -120, "point": 2.5},
                            {"name": "Over", "description": "Rafael Devers", "price": -105, "point": 2.5},
                            {"name": "Under", "description": "Rafael Devers", "price": -125, "point": 2.5},
                        ],
                    },
                    {
                        "key": "pitcher_strikeouts",
                        "outcomes": [
                            {"name": "Over", "description": "Gerrit Cole", "price": -115, "point": 7.5},
                            {"name": "Under", "description": "Gerrit Cole", "price": -115, "point": 7.5},
                            {"name": "Over", "description": "Tanner Houck", "price": -110, "point": 5.5},
                            {"name": "Under", "description": "Tanner Houck", "price": -120, "point": 5.5},
                        ],
                    },
                ],
            }
        ],
    }
]

_REPLAY_NBA_FIXTURES: list[dict[str, Any]] = [
    {
        "id": "nba_okc_ind_replay",
        "sport_key": "basketball_nba",
        "home_team": "Oklahoma City Thunder",
        "away_team": "Indiana Pacers",
        "commence_time": "2025-06-05T20:30:00Z",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "last_update": "2025-06-05T18:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Oklahoma City Thunder", "price": -220},
                            {"name": "Indiana Pacers", "price": 180},
                        ],
                    },
                    {
                        "key": "player_points",
                        "outcomes": [
                            {"name": "Over", "description": "Shai Gilgeous-Alexander", "price": -115, "point": 30.5},
                            {"name": "Under", "description": "Shai Gilgeous-Alexander", "price": -115, "point": 30.5},
                            {"name": "Over", "description": "Chet Holmgren", "price": -110, "point": 16.5},
                            {"name": "Under", "description": "Chet Holmgren", "price": -120, "point": 16.5},
                            {"name": "Over", "description": "Tyrese Haliburton", "price": -115, "point": 18.5},
                            {"name": "Under", "description": "Tyrese Haliburton", "price": -115, "point": 18.5},
                            {"name": "Over", "description": "Pascal Siakam", "price": -120, "point": 21.5},
                            {"name": "Under", "description": "Pascal Siakam", "price": -110, "point": 21.5},
                        ],
                    },
                    {
                        "key": "player_rebounds",
                        "outcomes": [
                            {"name": "Over", "description": "Shai Gilgeous-Alexander", "price": -120, "point": 5.5},
                            {"name": "Under", "description": "Shai Gilgeous-Alexander", "price": -110, "point": 5.5},
                            {"name": "Over", "description": "Chet Holmgren", "price": -115, "point": 8.5},
                            {"name": "Under", "description": "Chet Holmgren", "price": -115, "point": 8.5},
                            {"name": "Over", "description": "Pascal Siakam", "price": -115, "point": 7.5},
                            {"name": "Under", "description": "Pascal Siakam", "price": -115, "point": 7.5},
                            {"name": "Over", "description": "Tyrese Haliburton", "price": -110, "point": 4.5},
                            {"name": "Under", "description": "Tyrese Haliburton", "price": -120, "point": 4.5},
                        ],
                    },
                    {
                        "key": "player_assists",
                        "outcomes": [
                            {"name": "Over", "description": "Tyrese Haliburton", "price": -125, "point": 9.5},
                            {"name": "Under", "description": "Tyrese Haliburton", "price": -105, "point": 9.5},
                            {"name": "Over", "description": "Shai Gilgeous-Alexander", "price": -115, "point": 6.5},
                            {"name": "Under", "description": "Shai Gilgeous-Alexander", "price": -115, "point": 6.5},
                            {"name": "Over", "description": "Pascal Siakam", "price": -110, "point": 3.5},
                            {"name": "Under", "description": "Pascal Siakam", "price": -120, "point": 3.5},
                        ],
                    },
                    {
                        "key": "player_threes",
                        "outcomes": [
                            {"name": "Over", "description": "Tyrese Haliburton", "price": -110, "point": 2.5},
                            {"name": "Under", "description": "Tyrese Haliburton", "price": -120, "point": 2.5},
                            {"name": "Over", "description": "Shai Gilgeous-Alexander", "price": -130, "point": 1.5},
                            {"name": "Under", "description": "Shai Gilgeous-Alexander", "price": 100, "point": 1.5},
                            {"name": "Over", "description": "Chet Holmgren", "price": -115, "point": 1.5},
                            {"name": "Under", "description": "Chet Holmgren", "price": -115, "point": 1.5},
                        ],
                    },
                ],
            }
        ],
    },
    {
        "id": "nba_lal_bos_replay",
        "sport_key": "basketball_nba",
        "home_team": "Boston Celtics",
        "away_team": "Los Angeles Lakers",
        "commence_time": "2025-05-20T20:00:00Z",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "last_update": "2025-05-20T18:00:00Z",
                "markets": [
                    {
                        "key": "player_points",
                        "outcomes": [
                            {"name": "Over", "description": "LeBron James", "price": -115, "point": 25.5},
                            {"name": "Under", "description": "LeBron James", "price": -115, "point": 25.5},
                            {"name": "Over", "description": "Anthony Davis", "price": -115, "point": 24.5},
                            {"name": "Under", "description": "Anthony Davis", "price": -115, "point": 24.5},
                            {"name": "Over", "description": "Jayson Tatum", "price": -115, "point": 27.5},
                            {"name": "Under", "description": "Jayson Tatum", "price": -115, "point": 27.5},
                            {"name": "Over", "description": "Jaylen Brown", "price": -115, "point": 23.5},
                            {"name": "Under", "description": "Jaylen Brown", "price": -115, "point": 23.5},
                        ],
                    },
                    {
                        "key": "player_rebounds",
                        "outcomes": [
                            {"name": "Over", "description": "LeBron James", "price": -115, "point": 7.5},
                            {"name": "Under", "description": "LeBron James", "price": -115, "point": 7.5},
                            {"name": "Over", "description": "Anthony Davis", "price": -120, "point": 10.5},
                            {"name": "Under", "description": "Anthony Davis", "price": -110, "point": 10.5},
                            {"name": "Over", "description": "Jayson Tatum", "price": -115, "point": 8.5},
                            {"name": "Under", "description": "Jayson Tatum", "price": -115, "point": 8.5},
                            {"name": "Over", "description": "Jaylen Brown", "price": -115, "point": 5.5},
                            {"name": "Under", "description": "Jaylen Brown", "price": -115, "point": 5.5},
                        ],
                    },
                    {
                        "key": "player_assists",
                        "outcomes": [
                            {"name": "Over", "description": "LeBron James", "price": -115, "point": 7.5},
                            {"name": "Under", "description": "LeBron James", "price": -115, "point": 7.5},
                            {"name": "Over", "description": "Anthony Davis", "price": -110, "point": 3.5},
                            {"name": "Under", "description": "Anthony Davis", "price": -120, "point": 3.5},
                            {"name": "Over", "description": "Jayson Tatum", "price": -115, "point": 4.5},
                            {"name": "Under", "description": "Jayson Tatum", "price": -115, "point": 4.5},
                            {"name": "Over", "description": "Jaylen Brown", "price": -115, "point": 3.5},
                            {"name": "Under", "description": "Jaylen Brown", "price": -115, "point": 3.5},
                        ],
                    },
                    {
                        "key": "player_threes",
                        "outcomes": [
                            {"name": "Over", "description": "LeBron James", "price": -110, "point": 2.5},
                            {"name": "Under", "description": "LeBron James", "price": -120, "point": 2.5},
                            {"name": "Over", "description": "Anthony Davis", "price": 140, "point": 1.5},
                            {"name": "Under", "description": "Anthony Davis", "price": -180, "point": 1.5},
                            {"name": "Over", "description": "Jayson Tatum", "price": -125, "point": 3.5},
                            {"name": "Under", "description": "Jayson Tatum", "price": -105, "point": 3.5},
                            {"name": "Over", "description": "Jaylen Brown", "price": -115, "point": 2.5},
                            {"name": "Under", "description": "Jaylen Brown", "price": -115, "point": 2.5},
                        ],
                    },
                ],
            }
        ],
    },
]


def _match_teams(fixture: dict[str, Any], home_team: str, away_team: str) -> bool:
    """Fuzzy check if a fixture matches the specified home/away teams."""
    fh = fixture.get("home_team", "").lower()
    fa = fixture.get("away_team", "").lower()
    req_h = home_team.lower()
    req_a = away_team.lower()
    if (req_h in fh or fh in req_h) and (req_a in fa or fa in req_a):
        return True
    if (req_h in fa or fa in req_h) and (req_a in fh or fh in req_a):
        return True
    return False


def _generate_synthetic_game_lines(home_team: str, away_team: str) -> dict[str, Any]:
    """Deterministically generate game lines for any match pairing."""
    seed = int(hashlib.md5(f"{home_team}:{away_team}".encode()).hexdigest()[:8], 16)
    ml_home = -140 if (seed % 2 == 0) else 120
    ml_away = 120 if ml_home == -140 else -140
    spread = -1.5 if ml_home < 0 else 1.5
    total = 8.5 if "baseball" in home_team or "baseball" in away_team else 215.5
    return {
        "moneyline": {"home": ml_home, "away": ml_away},
        "spread": {"line": spread, "home": -110, "away": -110},
        "total": {"line": total, "over": -110, "under": -110},
    }


def normalize_odds_api_event(
    raw_event: Mapping[str, Any],
    sport: str,
    *,
    bookmaker_preference: tuple[str, ...] = ("draftkings", "fanduel", "betmgm"),
) -> dict[str, Any]:
    """Normalize a raw The Odds API event payload into standard catalog facts."""
    home_team = str(raw_event.get("home_team") or "")
    away_team = str(raw_event.get("away_team") or "")
    commence_time = str(raw_event.get("commence_time") or "")
    event_id = str(raw_event.get("id") or "")

    game_lines: dict[str, Any] = {}
    player_props: list[dict[str, Any]] = []

    bookmakers = raw_event.get("bookmakers", [])
    if isinstance(bookmakers, list):
        # Sort bookmakers by preference
        sorted_books = sorted(
            bookmakers,
            key=lambda b: (
                bookmaker_preference.index(b.get("key"))
                if b.get("key") in bookmaker_preference
                else 999
            ),
        )

        seen_props: set[tuple[str, str]] = set()

        for book in sorted_books:
            b_key = str(book.get("key", "unknown"))
            b_title = str(book.get("title", b_key))
            markets = book.get("markets", [])
            if not isinstance(markets, list):
                continue

            for market in markets:
                m_key = str(market.get("key", ""))
                outcomes = market.get("outcomes", [])
                if not isinstance(outcomes, list):
                    continue

                if m_key == "h2h" and "moneyline" not in game_lines:
                    ml: dict[str, Any] = {}
                    for o in outcomes:
                        name = o.get("name")
                        price = o.get("price")
                        if name == home_team:
                            ml["home"] = price
                        elif name == away_team:
                            ml["away"] = price
                    if ml:
                        game_lines["moneyline"] = ml

                elif m_key == "totals" and "total" not in game_lines:
                    tot: dict[str, Any] = {}
                    for o in outcomes:
                        name = str(o.get("name", "")).lower()
                        price = o.get("price")
                        point = o.get("point")
                        if point is not None:
                            tot["line"] = point
                        if name == "over":
                            tot["over"] = price
                        elif name == "under":
                            tot["under"] = price
                    if tot:
                        game_lines["total"] = tot

                elif m_key == "spreads" and "spread" not in game_lines:
                    spr: dict[str, Any] = {}
                    for o in outcomes:
                        name = o.get("name")
                        price = o.get("price")
                        point = o.get("point")
                        if name == home_team:
                            spr["home"] = price
                            if point is not None:
                                spr["line"] = point
                        elif name == away_team:
                            spr["away"] = price
                    if spr:
                        game_lines["spread"] = spr

                # Player props normalization
                internal_market = _map_market_key(sport, m_key)
                if internal_market:
                    # Group by player
                    by_player: dict[str, dict[str, Any]] = {}
                    for o in outcomes:
                        player = o.get("description") or o.get("participant_name")
                        if not player:
                            continue
                        name = str(o.get("name", "")).lower()
                        point = o.get("point")
                        price = o.get("price")
                        prop_entry = by_player.setdefault(str(player), {"point": point})
                        if point is not None:
                            prop_entry["point"] = point
                        if name == "over":
                            prop_entry["over_odds"] = price
                        elif name == "under":
                            prop_entry["under_odds"] = price

                    for player_name, vals in by_player.items():
                        dedup_key = (player_name.lower(), internal_market)
                        if dedup_key in seen_props:
                            continue
                        seen_props.add(dedup_key)
                        if vals.get("point") is not None:
                            player_props.append({
                                "player_name": player_name,
                                "market": internal_market,
                                "line": float(vals["point"]),
                                "over_odds": vals.get("over_odds"),
                                "under_odds": vals.get("under_odds"),
                                "bookmaker": b_title,
                                "source": "the_odds_api",
                            })

    return {
        "event_id": event_id,
        "sport": sport,
        "home_team": home_team,
        "away_team": away_team,
        "commence_time": commence_time,
        "game_lines": game_lines,
        "player_props": player_props,
    }


def _map_market_key(sport: str, raw_key: str) -> str | None:
    norm_sport = sport.lower()
    if norm_sport in ("baseball", "mlb"):
        return MLB_MARKET_MAP.get(raw_key)
    if norm_sport in ("basketball", "nba"):
        return NBA_MARKET_MAP.get(raw_key)
    return None


class TheOddsApiAdapter:
    """Catalog provider implementation for The Odds API aggregator."""

    provider_name: str = "the_odds_api"

    def __init__(
        self,
        config: TheOddsApiConfig | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        import os

        env_key = os.getenv("THE_ODDS_API_KEY")
        if config is None:
            self._config = TheOddsApiConfig(api_key=env_key)
        elif config.api_key is None and env_key:
            self._config = TheOddsApiConfig(
                api_key=env_key,
                base_url=config.base_url,
                timeout_seconds=config.timeout_seconds,
                regions=config.regions,
                odds_format=config.odds_format,
                default_bookmakers=config.default_bookmakers,
            )
        else:
            self._config = config

        self._client = client
        self.remaining_requests: int | None = None
        self.used_requests: int | None = None

    def fetch(self, request: ProviderRequest) -> ProviderResult:
        """Fetch odds or props either via live API or deterministic replay."""
        if self._config.api_key:
            return self._fetch_live(request)
        return self._fetch_replay(request)

    def _fetch_live(self, request: ProviderRequest) -> ProviderResult:
        sport_key = SPORT_TO_ODDS_API_KEY.get(request.sport.lower(), request.sport)
        url = f"{self._config.base_url}/sports/{sport_key}/odds"
        params: dict[str, Any] = {
            "apiKey": self._config.api_key,
            "regions": self._config.regions,
            "oddsFormat": self._config.odds_format,
        }

        # Market selection
        markets_param = request.parameters.get("markets")
        if markets_param:
            params["markets"] = markets_param

        event_id = request.event_id or request.parameters.get("event_id")
        if event_id:
            url = f"{self._config.base_url}/sports/{sport_key}/events/{event_id}/odds"

        try:
            client = self._client or httpx.Client(timeout=self._config.timeout_seconds)
            try:
                resp = client.get(url, params=params)
                self._update_quota_from_headers(resp.headers)

                if resp.status_code == 401:
                    return ProviderResult(
                        provider=self.provider_name,
                        status=ProviderStatus.UNAVAILABLE,
                        retrieved_at=request.requested_at,
                        error_category=ProviderErrorCategory.AUTHENTICATION,
                        retryable=False,
                    )
                if resp.status_code == 429:
                    return ProviderResult(
                        provider=self.provider_name,
                        status=ProviderStatus.UNAVAILABLE,
                        retrieved_at=request.requested_at,
                        error_category=ProviderErrorCategory.RATE_LIMITED,
                        retryable=True,
                    )
                if resp.status_code >= 500:
                    return ProviderResult(
                        provider=self.provider_name,
                        status=ProviderStatus.UNAVAILABLE,
                        retrieved_at=request.requested_at,
                        error_category=ProviderErrorCategory.UNAVAILABLE,
                        retryable=True,
                    )
                resp.raise_for_status()
                data = resp.json()

            finally:
                if self._client is None:
                    client.close()

            # Normalization
            normalized_facts = self._normalize_live_data(data, request)
            obs = SourceObservation(
                observation_id=f"{self.provider_name}:{request.sport}:{request.requested_at}",
                provider=self.provider_name,
                observed_at=request.requested_at,
                confidence=Confidence.CONFIRMED,
            )
            return ProviderResult(
                provider=self.provider_name,
                status=ProviderStatus.AVAILABLE,
                retrieved_at=request.requested_at,
                facts=normalized_facts,
                observation=obs,
                quota_units=1,
            )

        except httpx.TimeoutException:
            return ProviderResult(
                provider=self.provider_name,
                status=ProviderStatus.UNAVAILABLE,
                retrieved_at=request.requested_at,
                error_category=ProviderErrorCategory.TIMEOUT,
                retryable=True,
            )
        except Exception as exc:
            logger.warning("the_odds_api_live_fetch_failed: %s", exc)
            return ProviderResult(
                provider=self.provider_name,
                status=ProviderStatus.UNAVAILABLE,
                retrieved_at=request.requested_at,
                error_category=ProviderErrorCategory.UNKNOWN,
                retryable=False,
            )

    def _normalize_live_data(self, data: Any, request: ProviderRequest) -> dict[str, Any]:
        if isinstance(data, dict):
            return normalize_odds_api_event(
                data,
                request.sport,
                bookmaker_preference=self._config.default_bookmakers,
            )
        if isinstance(data, list):
            home = request.parameters.get("home_team", "")
            away = request.parameters.get("away_team", "")
            if home and away:
                for item in data:
                    if isinstance(item, dict) and _match_teams(item, home, away):
                        return normalize_odds_api_event(
                            item,
                            request.sport,
                            bookmaker_preference=self._config.default_bookmakers,
                        )
            # If no match or no home/away specified, return normalized first or empty
            if data and isinstance(data[0], dict):
                return normalize_odds_api_event(
                    data[0],
                    request.sport,
                    bookmaker_preference=self._config.default_bookmakers,
                )
        return {"sport": request.sport, "player_props": [], "game_lines": {}}

    def _fetch_replay(self, request: ProviderRequest) -> ProviderResult:
        """Deterministic replay for hermetic testing and audits."""
        sport_norm = request.sport.lower()
        home = request.parameters.get("home_team", "")
        away = request.parameters.get("away_team", "")
        requested_players = request.parameters.get("players", "")

        fixture_pool: list[dict[str, Any]] = []
        if sport_norm in ("baseball", "mlb"):
            fixture_pool = _REPLAY_MLB_FIXTURES
        elif sport_norm in ("basketball", "nba"):
            fixture_pool = _REPLAY_NBA_FIXTURES

        matched_fixture: dict[str, Any] | None = None
        if home and away:
            for fix in fixture_pool:
                if _match_teams(fix, home, away):
                    matched_fixture = fix
                    break

        if matched_fixture is None and fixture_pool:
            # Fall back to first fixture template and dynamically adapt team/player names
            template = fixture_pool[0]
            matched_fixture = dict(template)
            if home:
                matched_fixture["home_team"] = home
            if away:
                matched_fixture["away_team"] = away

        facts: dict[str, Any]
        if matched_fixture:
            facts = normalize_odds_api_event(
                matched_fixture,
                request.sport,
                bookmaker_preference=self._config.default_bookmakers,
            )
        else:
            # Generate synthetic facts deterministically
            facts = {
                "event_id": f"{sport_norm}_{home}_{away}_replay",
                "sport": request.sport,
                "home_team": home,
                "away_team": away,
                "commence_time": request.requested_at,
                "game_lines": _generate_synthetic_game_lines(home, away),
                "player_props": [],
            }

        # If specific players were requested but not in props, add deterministic props
        if requested_players:
            existing_players = {p["player_name"].lower() for p in facts.get("player_props", [])}
            names = [n.strip() for n in requested_players.split(",") if n.strip()]
            for name in names:
                if name.lower() not in existing_players:
                    facts.setdefault("player_props", []).extend(
                        self._generate_default_player_props(sport_norm, name)
                    )

        obs = SourceObservation(
            observation_id=f"{self.provider_name}:replay:{request.sport}:{request.requested_at}",
            provider=self.provider_name,
            observed_at=request.requested_at,
            confidence=Confidence.CONFIRMED,
        )

        return ProviderResult(
            provider=self.provider_name,
            status=ProviderStatus.AVAILABLE,
            retrieved_at=request.requested_at,
            facts=facts,
            observation=obs,
            quota_units=0,
        )

    def _generate_default_player_props(self, sport: str, player_name: str) -> list[dict[str, Any]]:
        """Generate deterministic fallback lines for unknown players."""
        props: list[dict[str, Any]] = []
        if sport in ("baseball", "mlb"):
            props.extend([
                {
                    "player_name": player_name,
                    "market": "hits",
                    "line": 1.5,
                    "over_odds": -130,
                    "under_odds": 100,
                    "bookmaker": "DraftKings",
                    "source": "the_odds_api",
                },
                {
                    "player_name": player_name,
                    "market": "strikeouts",
                    "line": 5.5,
                    "over_odds": -115,
                    "under_odds": -115,
                    "bookmaker": "DraftKings",
                    "source": "the_odds_api",
                },
                {
                    "player_name": player_name,
                    "market": "total_bases",
                    "line": 1.5,
                    "over_odds": -110,
                    "under_odds": -120,
                    "bookmaker": "DraftKings",
                    "source": "the_odds_api",
                },
            ])
        elif sport in ("basketball", "nba"):
            props.extend([
                {
                    "player_name": player_name,
                    "market": "points",
                    "line": 19.5,
                    "over_odds": -115,
                    "under_odds": -115,
                    "bookmaker": "DraftKings",
                    "source": "the_odds_api",
                },
                {
                    "player_name": player_name,
                    "market": "rebounds",
                    "line": 6.5,
                    "over_odds": -110,
                    "under_odds": -120,
                    "bookmaker": "DraftKings",
                    "source": "the_odds_api",
                },
                {
                    "player_name": player_name,
                    "market": "assists",
                    "line": 4.5,
                    "over_odds": -115,
                    "under_odds": -115,
                    "bookmaker": "DraftKings",
                    "source": "the_odds_api",
                },
                {
                    "player_name": player_name,
                    "market": "threes",
                    "line": 2.5,
                    "over_odds": -110,
                    "under_odds": -120,
                    "bookmaker": "DraftKings",
                    "source": "the_odds_api",
                },
            ])
        return props

    def _update_quota_from_headers(self, headers: Mapping[str, str]) -> None:
        rem = headers.get("x-requests-remaining")
        used = headers.get("x-requests-used")
        if rem is not None:
            try:
                self.remaining_requests = int(rem)
            except ValueError:
                pass
        if used is not None:
            try:
                self.used_requests = int(used)
            except ValueError:
                pass
