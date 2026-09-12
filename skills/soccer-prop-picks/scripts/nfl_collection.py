"""Grounded NFL collection using the application's existing LLM clients."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse, urlunparse
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, ValidationError

from diagnostics_support import diagnostic_stage, emit, error_info, submit_with_context

from nfl_domain import (
    NFL_GAME_MARKETS,
    NFL_PLAYER_MARKETS,
    resolve_team,
    timestamp,
    web_url,
)


class NflGame(BaseModel):
    home_team: str
    away_team: str
    event_date: str
    kickoff_utc: str | None = None
    season: int
    season_type: Literal["regular", "postseason", "preseason"]
    status: Literal["scheduled", "in_progress", "final", "postponed", "cancelled"]
    neutral_venue: bool = False
    source_urls: list[str] = Field(default_factory=list)


class NflGameLog(BaseModel):
    date: str
    season: int
    played: bool
    season_type: Literal["regular", "postseason", "preseason"]
    passing_yards: float | None = None
    passing_touchdowns: float | None = None
    interceptions_thrown: float | None = None
    rushing_yards: float | None = None
    receiving_yards: float | None = None
    receptions: float | None = None
    scorer_touchdowns: float | None = None


class NflPlayer(BaseModel):
    player_name: str
    team: str
    position: str
    injury_status: str = "unknown"
    opportunity_ratio: float | None = None
    opponent_factor: float | None = None
    game_logs: list[NflGameLog] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class NflTeam(BaseModel):
    team: str
    season: int | None = None
    games_played: int | None = None
    points_for_avg: float | None = None
    points_against_avg: float | None = None
    points_for_last5: float | None = None
    points_against_last5: float | None = None
    qb_status: str = "unknown"
    rest_days: float | None = None
    source_urls: list[str] = Field(default_factory=list)


class NflWeather(BaseModel):
    wind_kph: float | None = None
    roof_closed: bool | None = None


class NflContext(BaseModel):
    game: NflGame | None = None
    players: list[NflPlayer] = Field(default_factory=list)
    teams: list[NflTeam] = Field(default_factory=list)
    weather: NflWeather = Field(default_factory=NflWeather)


class NflOffer(BaseModel):
    market: Literal[
        "passing_yards",
        "passing_touchdowns",
        "interceptions_thrown",
        "rushing_yards",
        "receiving_yards",
        "receptions",
        "anytime_touchdown",
        "moneyline",
        "spread",
        "total",
    ]
    subject_name: str
    selection: Literal["home", "away", "over", "under", "yes"]
    line: float | None = None
    sportsbook: str
    odds_decimal: float
    source_url: str
    observed_at: str
    period: Literal["full_game"]
    includes_overtime: bool
    is_live: bool
    is_primary: bool


class NflOffers(BaseModel):
    offers: list[NflOffer] = Field(default_factory=list)


_OFFER_KEY_ALIASES = {
    "book": "sportsbook",
    "operator": "sportsbook",
    "price_decimal": "odds_decimal",
    "observed_at_utc": "observed_at",
}
_MARKET_ALIASES = {
    "anytime_td": "anytime_touchdown",
    "anytime_tds": "anytime_touchdown",
    "interceptions": "interceptions_thrown",
    "passing_td": "passing_touchdowns",
}


def normalize_offer_payload(raw_offer: dict) -> dict:
    """Normalize only unambiguous provider spelling differences before validation."""
    normalized = {
        _OFFER_KEY_ALIASES.get(str(key).casefold(), key): value
        for key, value in raw_offer.items()
    }
    if isinstance(normalized.get("market"), str):
        market = normalized["market"].casefold().strip().replace(" ", "_").replace("-", "_")
        normalized["market"] = _MARKET_ALIASES.get(market, market)
    if isinstance(normalized.get("selection"), str):
        normalized["selection"] = normalized["selection"].casefold().strip()
    if isinstance(normalized.get("sportsbook"), str):
        normalized["sportsbook"] = normalized["sportsbook"].strip()
    return normalized


@lru_cache(maxsize=256)
def _resolve_citation_url(url):
    # Resolve only Google's citation wrapper, without following the destination.
    parsed = urlparse(url)
    if (
        parsed.hostname != "vertexaisearch.cloud.google.com"
        or not parsed.path.startswith("/grounding-api-redirect/")
    ):
        return url
    import httpx

    try:
        with httpx.Client(timeout=5, follow_redirects=False) as client:
            with client.stream("GET", url) as response:
                destination = response.headers.get("location")
                if response.is_redirect and web_url(destination):
                    return destination
    except httpx.HTTPError:
        pass
    return url


def _canonical_url(url):
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.params,
            parsed.query,
            "",
        )
    )


def _source_urls(client, *, referenced_urls=None):
    urls = {s.url for s in getattr(client, "last_sources", []) if web_url(s.url)}
    if (
        getattr(client, "last_research_evidence", None)
        and referenced_urls is not None
        and set(referenced_urls).issubset(urls)
    ):
        return {url for url in urls if not _is_search_url(url)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [submit_with_context(pool, _resolve_citation_url, url) for url in sorted(urls)]
        pairs = zip(sorted(urls), (future.result() for future in futures))
        # Existing clients may expose search queries as fallback "sources".
        # Those are discovery hints, not evidence pages.
        return {
            url
            for original, resolved in pairs
            if not _is_search_url(resolved) and not _is_search_url(original)
            for url in (original, resolved)
        }


def _is_search_url(url):
    host = (urlparse(url).hostname or "").removeprefix("www.")
    return host in {"google.com", "bing.com", "search.yahoo.com", "duckduckgo.com"}


def _grounded_sources(values, verified):
    # The model naming a URL is insufficient: require a provider search citation.
    keys = {_canonical_url(url) for url in verified}
    return [url for url in values if web_url(url) and _canonical_url(url) in keys]


class NflCollector:
    def __init__(self, client, *, timezone_name=None):
        self.client = client
        self.last_provider_error = None
        self.timezone_name = (
            timezone_name or os.getenv("COLMILLO_TIMEZONE") or "America/Chicago"
        )

    @diagnostic_stage("nfl_provider", sport="nfl")
    def _generate(self, *, system_prompt, user_prompt, schema, temperature=0):
        research = getattr(self.client, "research_then_extract", None)
        if not callable(research):
            return self.client.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
                temperature=temperature,
            )
        from sport_enrichment_config import get_enrichment_config

        task = json.loads(user_prompt)
        task.pop("schema", None)
        fields = {
            name: list(definition.get("properties", {}))
            for name, definition in schema.get("$defs", {}).items()
        }
        if "offers" in schema.get("properties", {}):
            game = task["game"]
            markets = ", ".join(task["markets"])
            prompt = (
                f"Use Google Search to find current full-game pregame MAIN {markets} offers for "
                f"{game['away_team']} at {game['home_team']} on {game['event_date']}. "
                f"Current retrieval time: {task['request']['now_utc']}. "
                "Write a short sourced odds brief in prose or tables. Focus only on the requested betting markets. "
                "For each available quote, name the sportsbook, exact selection, signed spread or numeric line "
                "where applicable, and price. Cite the specific source for that quote and applicable overtime rules. "
                "Keep each book's offer intact. Do not invent missing quotes or prices; report unavailable markets. "
                "Only main lines, no alternate, in-play or partial-game markets. "
                "The home team is "
                + game["home_team"]
                + "; the away team is "
                + game["away_team"]
                + ". "
                "For extraction use home/away selections for moneyline/spread, over/under for numeric props/totals, "
                "yes for anytime_touchdown, null lines for moneyline/anytime_touchdown, and full_game as period. "
                "For total subject_name use exactly "
                + game["home_team"]
                + " v "
                + game["away_team"]
                + "."
            )
            if any(m in NFL_PLAYER_MARKETS for m in task["markets"]):
                prompt += "\nPlayers from the verified fixture roster: " + ", ".join(
                    task["players"]
                )
            return research(research_prompt=prompt, schema=schema)
        prompt = (
            "Use Google Search to research the requested NFL facts. Write a sourced research brief in prose or tables, not JSON. "
            "Cite a source for each fixture, player, team or sportsbook offer. Clearly mark facts you cannot find. "
            "Do not estimate missing stats or offers. Include the current observation time when retrieving live odds.\n"
            + get_enrichment_config("nfl").system_prompt_guidance
            + "\nTask: "
            + json.dumps(task)
            + "\nFields to look for (only report those supported by sources): "
            + json.dumps(fields)
        )
        return research(research_prompt=prompt, schema=schema)

    @classmethod
    def from_env(cls, *, provider=None, model=None, timezone_name=None):
        from match_discovery import MatchDiscoveryClient

        configured = MatchDiscoveryClient.from_env(
            provider=provider, model=model, max_output_tokens=16000
        )
        return cls(configured.client, timezone_name=timezone_name)

    def __call__(self, *, home_team, away_team, match_date, league=None):
        from sport_enrichment_config import get_enrichment_config

        self.last_provider_error = None
        now = datetime.now(timezone.utc).isoformat()
        guidance = get_enrichment_config("nfl").system_prompt_guidance
        request = {
            "home_team": resolve_team(home_team),
            "away_team": resolve_team(away_team),
            "event_date": match_date,
            "date_timezone": self.timezone_name,
            "now_utc": now,
            "league": "nfl",
        }
        system = guidance + (
            "\nReturn only JSON matching the schema. Search now; never use remembered odds or rosters. "
            "Use exact URLs from your search citations for source_urls and source_url. "
            "Leave unavailable fields null and unavailable lists empty."
        )
        context_raw = self._generate(
            system_prompt=system,
            user_prompt=json.dumps(
                {
                    "task": "Verify this NFL fixture and collect context for both teams, starting QBs and leading RB/WR/TE players. Return up to 5 most recent completed regular/postseason game logs per player, excluding preseason. Use actual game dates and season years. If no verified upcoming fixture, return game=null. Follow enum spellings exactly: scheduled and regular/postseason. The task is pregame: do not use this fixture's result or statistics.",
                    "request": request,
                    "schema": NflContext.model_json_schema(),
                }
            ),
            schema=NflContext.model_json_schema(),
            temperature=0,
        )
        data = NflContext.model_validate(
            {
                **context_raw,
                "players": [],
                "teams": [],
                "weather": context_raw.get("weather") or {},
            }
        ).model_dump()
        data["collected_game"] = dict(data["game"]) if data["game"] else None
        data.update(
            offers=[], exclusions=[], provider_statuses={}, grounding_sources=[]
        )
        data["research_evidence"] = {
            "context": getattr(self.client, "last_research_evidence", None)
        }
        for key, model in (("players", NflPlayer), ("teams", NflTeam)):
            for entity in context_raw.get(key) or []:
                try:
                    data[key].append(model.model_validate(entity).model_dump())
                except ValidationError:
                    data["exclusions"].append(
                        {
                            "subject": key,
                            "reason": "An incomplete entity was excluded from collection.",
                        }
                    )
        referenced = (data.get("game") or {}).get("source_urls", []) + [
            url
            for entity in data["players"] + data["teams"]
            for url in entity["source_urls"]
        ]
        verified = _source_urls(self.client, referenced_urls=referenced)
        data["grounding_sources"] = sorted(verified)
        game = data.get("game")
        if game:
            game["source_urls"] = _grounded_sources(game["source_urls"], verified)
            game["home_team"] = resolve_team(game["home_team"])
            game["away_team"] = resolve_team(game["away_team"])
            kickoff = timestamp(game.get("kickoff_utc"))
            if (
                {game["home_team"], game["away_team"]}
                != {request["home_team"], request["away_team"]}
                or not kickoff
                or kickoff.astimezone(ZoneInfo(self.timezone_name)).date().isoformat()
                != match_date
                or not game["source_urls"]
            ):
                data["game"] = None
            else:
                game["event_date"] = match_date
        if not data["game"]:
            data["exclusions"].append(
                {
                    "subject": "game",
                    "reason": "Fixture could not be verified with provider search citations.",
                }
            )
            return data
        for entity in data["players"] + data["teams"]:
            entity["source_urls"] = _grounded_sources(entity["source_urls"], verified)
            entity["team"] = resolve_team(entity["team"])
        data["provider_statuses"]["context"] = "ok"
        for markets in (NFL_GAME_MARKETS, NFL_PLAYER_MARKETS):
            self._collect_offer_group(data, request, system, markets)
        data["provider_statuses"]["offers"] = "ok" if data["offers"] else "unavailable"
        return data

    def _collect_offer_group(self, data, request, system, markets):
        game = data["game"]
        group = "game_offers" if markets == NFL_GAME_MARKETS else "player_offers"
        starting_count = len(data["offers"])
        try:
            raw = self._generate(
                system_prompt=system,
                user_prompt=json.dumps(
                    {
                        "task": "Find current full-game pregame sportsbook offers for this verified fixture, only for the markets in the supplied markets array. Cite the specific sportsbook rules confirming whether overtime is included. Return only primary lines, with exact named book, selection, decimal price and observed timestamp. No consensus prices, live, alternate, preseason or partial-game markets. Never infer an offer from stats. Only return offers that include overtime. Anytime scorer excludes passing TDs. Use null line for moneyline and anytime_touchdown; yes for anytime selection, home/away for spread and moneyline, over/under otherwise. Spread line is signed for the selected team. For total, subject_name is exactly home_team + ' v ' + away_team. Return both offered sides when available.",
                        "request": request,
                        "game": game,
                        "players": [p["player_name"] for p in data["players"]],
                        "markets": markets,
                        "schema": NflOffers.model_json_schema(),
                    }
                ),
                schema=NflOffers.model_json_schema(),
                temperature=0,
            )
            verified = _source_urls(
                self.client,
                referenced_urls=[
                    o.get("source_url")
                    for o in raw.get("offers", [])
                    if isinstance(o, dict)
                ],
            )
            data["research_evidence"][group] = getattr(
                self.client, "last_research_evidence", None
            )
            data["grounding_sources"] = sorted(
                set(data["grounding_sources"]) | verified
            )
            for raw_offer in raw.get("offers", []):
                try:
                    offer = NflOffer.model_validate(normalize_offer_payload(raw_offer)).model_dump()
                except ValidationError:
                    data["exclusions"].append(
                        {"subject": "offer", "reason": "Malformed sportsbook offer."}
                    )
                    continue
                if offer["market"] not in markets:
                    continue
                if not _grounded_sources([offer["source_url"]], verified):
                    data["exclusions"].append(
                        {
                            "subject": offer["subject_name"],
                            "reason": "Offer URL was not backed by a provider search citation.",
                        }
                    )
                    continue
                data["offers"].append(offer)
            data["provider_statuses"][group] = (
                "ok" if len(data["offers"]) > starting_count else "unavailable"
            )
        except Exception as exc:
            self.last_provider_error = exc
            data["provider_statuses"][group] = "unavailable"
            data["research_evidence"][group] = getattr(
                self.client, "last_research_evidence", None
            )
            data.setdefault("provider_errors", {})[group] = {
                **error_info(exc),
                "type": type(exc).__name__,
                "cause_type": type(exc.__cause__).__name__ if exc.__cause__ else None,
                "research_cited": bool(data["research_evidence"][group]),
            }
            emit("nfl_provider_failed", stage=group, level="WARNING", outcome="failed",
                 sport="nfl", **error_info(exc))
            data["exclusions"].append(
                {
                    "subject": group,
                    "reason": "Sportsbook collection unavailable; no odds were substituted.",
                }
            )
        return data
