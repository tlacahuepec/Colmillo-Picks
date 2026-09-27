"""Bounded public-page collection for Fanatics Markets.

This is a prediction-market source.  Its displayed contract prices must never be
treated as sportsbook odds.  The collector intentionally does not authenticate,
bypass location checks or challenges, or call undocumented private endpoints.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Iterable, Mapping

import httpx

from services.catalog.contracts import (
    CatalogEvent,
    CatalogSnapshot,
    CompletenessStatus,
    Confidence,
    PredictionMarketObservation,
    SourceObservation,
)
from services.catalog.providers import canonical_entity_id, canonical_ref


FANATICS_MARKETS_URL = "https://fanaticsmarkets.com/"
_MAX_RESPONSE_BYTES = 8_000_000
_NEXT_RSC_PUSH = re.compile(r'self\.__next_f\.push\(\[1,("(?:\\.|[^"\\])*")\]\)')


class FanaticsMarketsError(RuntimeError):
    """Safe, typed collection failure for the public Fanatics page."""


@dataclass(frozen=True)
class FanaticsCollectionResult:
    snapshots: tuple[CatalogSnapshot, ...]
    supplemental_signals: int
    unavailable_pages: int = 0


class _ScriptExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_script = False
        self._attrs: dict[str, str] = {}
        self._parts: list[str] = []
        self.scripts: list[tuple[dict[str, str], str]] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self._in_script = True
            self._attrs = {name: value or "" for name, value in attrs}
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_script:
            self.scripts.append((self._attrs, "".join(self._parts)))
            self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._parts.append(data)
        elif data.strip():
            self.text.append(data.strip())


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _walk(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _first_text(item: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = item.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, Mapping):
            nested = value.get("name") or value.get("displayName")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _start_time(item: Mapping[str, Any]) -> str | None:
    value = item.get("startTime") or item.get("start_time") or item.get("scheduledAt")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _sport_name(item: Mapping[str, Any]) -> str:
    raw = (_first_text(item, "sport", "sportName", "series") or "unknown").casefold()
    aliases = {
        "mlb": "baseball",
        "nfl": "nfl",
        "nba": "basketball",
        "wnba": "basketball",
        "mls": "soccer",
        "liga mx": "soccer",
        "premier league": "soccer",
        "english premier league": "soccer",
    }
    return aliases.get(raw, raw)


def _rsc_payloads(scripts: Iterable[tuple[dict[str, str], str]]) -> Iterable[Any]:
    """Extract JSON fragments from Next.js server-component script payloads."""
    decoder = json.JSONDecoder()
    for _attrs, script in scripts:
        for encoded in _NEXT_RSC_PUSH.findall(script):
            try:
                decoded = json.loads(encoded)
            except json.JSONDecodeError:
                continue
            for index, character in enumerate(decoded):
                if character not in "[{":
                    continue
                try:
                    value, _ = decoder.raw_decode(decoded[index:])
                except json.JSONDecodeError:
                    continue
                yield value


def _event_from_mapping(item: Mapping[str, Any], *, observed_at: str) -> CatalogEvent | None:
    home = _first_text(item, "home_team", "homeTeam", "home")
    away = _first_text(item, "away_team", "awayTeam", "away")
    matchup: Mapping[str, Any] = {}
    raw_matchup = item.get("matchupProps")
    if isinstance(raw_matchup, Mapping):
        matchup = raw_matchup
    home = home or _first_text(matchup.get("sideA", {}), "name", "shortName")
    away = away or _first_text(matchup.get("sideB", {}), "name", "shortName")
    start = _start_time(item) or _first_text(item, "event_date", "eventDate")
    if not home or not away or not start:
        return None
    sport = _sport_name(item)
    league = (_first_text(item, "league", "competition", "leagueName") or sport).casefold()
    native_id = _first_text(item, "event_id", "eventId", "id")
    event_id = canonical_entity_id(sport, "event", native_id, f"{home}-{away}-{start}")
    return CatalogEvent(
        event_id=event_id, sport=sport, league=league, start_time=start,
        status=(_first_text(item, "status") or "scheduled").casefold(),
        home_team=canonical_ref(sport, "team", display_name=home, provider="fanatics_markets"),
        away_team=canonical_ref(sport, "team", display_name=away, provider="fanatics_markets"),
        source_observation_ids=(f"fanatics_markets:{event_id}:{observed_at}",),
    )


def _markets_from_mapping(item: Mapping[str, Any], *, event_id: str, observed_at: str) -> list[PredictionMarketObservation]:
    raw_markets = item.get("markets") or item.get("contracts") or []
    if isinstance(raw_markets, Mapping):
        raw_markets = [
            {"marketType": market_type, "selections": selections}
            for market_type, selections in raw_markets.items()
        ]
    if not isinstance(raw_markets, list):
        return []
    output: list[PredictionMarketObservation] = []
    for index, market in enumerate(raw_markets):
        if not isinstance(market, Mapping):
            continue
        market_id = _first_text(market, "market_id", "marketId", "id") or f"{event_id}:market:{index}"
        selections = market.get("selections") or market.get("outcomes") or [market]
        if not isinstance(selections, list):
            selections = [market]
        for selection in selections:
            if not isinstance(selection, Mapping):
                continue
            label = _first_text(selection, "selection", "name", "label", "outcome", "title", "shortTitle")
            if not label:
                continue
            price = _first_text(selection, "price", "displayPrice", "yesPrice")
            if price is None and isinstance(selection.get("price"), (int, float)):
                price = str(selection["price"])
            if price is None and isinstance(selection.get("probability"), (int, float)):
                price = f"{float(selection['probability']) * 100:g}%"
            volume = _first_text(market, "volume", "displayVolume")
            if volume is None and isinstance(selection.get("totalVolume"), (int, float, str)):
                volume = str(selection["totalVolume"])
            output.append(PredictionMarketObservation(
                market_id=market_id,
                market_type=_first_text(market, "market_type", "marketType", "name", "title") or "contract",
                selection=label, displayed_price=price,
                volume=volume,
                status=_first_text(selection, "status") or _first_text(market, "status") or "available",
                observed_at=observed_at, source_url=FANATICS_MARKETS_URL,
            ))
    return output


class FanaticsMarketsCollector:
    """Fetch and normalize public, structured data embedded in the home page."""

    def __init__(self, *, client: httpx.Client | None = None, url: str = FANATICS_MARKETS_URL) -> None:
        self._client = client or httpx.Client(timeout=15, follow_redirects=True)
        self._url = url

    def collect(self, *, run_date: str) -> FanaticsCollectionResult:
        try:
            response = self._client.get(self._url, headers={"User-Agent": "Colmillo-Picks catalog refresher/1.0"})
        except httpx.HTTPError as exc:
            raise FanaticsMarketsError("Fanatics Markets was unavailable.") from exc
        if response.status_code in {401, 403, 429}:
            raise FanaticsMarketsError(f"Fanatics Markets rejected collection ({response.status_code}).")
        if response.status_code >= 400:
            raise FanaticsMarketsError(f"Fanatics Markets returned HTTP {response.status_code}.")
        if len(response.content) > _MAX_RESPONSE_BYTES:
            raise FanaticsMarketsError("Fanatics Markets response exceeded the collection limit.")

        observed_at = _now_utc()
        parser = _ScriptExtractor()
        parser.feed(response.text)
        payloads: list[Any] = []
        for attrs, script in parser.scripts:
            if attrs.get("type") not in {"application/json", "application/ld+json"}:
                continue
            try:
                payloads.append(json.loads(script))
            except json.JSONDecodeError:
                continue
        payloads.extend(_rsc_payloads(parser.scripts))

        snapshots: list[CatalogSnapshot] = []
        seen: set[str] = set()
        for payload in payloads:
            for item in _walk(payload):
                event = _event_from_mapping(item, observed_at=observed_at)
                if event is None or event.event_id in seen or run_date not in event.start_time:
                    continue
                seen.add(event.event_id)
                observation = SourceObservation(
                    observation_id=f"fanatics_markets:{event.event_id}:{observed_at}",
                    provider="fanatics_markets", observed_at=observed_at, source_url=self._url,
                    extraction_method="public_page", confidence=Confidence.LOW,
                )
                markets = _markets_from_mapping(item, event_id=event.event_id, observed_at=observed_at)
                snapshots.append(CatalogSnapshot(
                    snapshot_id=f"{event.event_id}:fanatics:{observed_at}", event=event,
                    created_at=observed_at, as_of=observed_at,
                    completeness=CompletenessStatus.PARTIAL,
                    prediction_markets=tuple(markets), source_observations=(observation,),
                    missing_fields=("lineups", "injuries", "official_odds", "form", "weather"),
                ))
        signals = sum(1 for value in parser.text if re.search(r"trending|promo|volume|mover", value, re.I))
        return FanaticsCollectionResult(tuple(snapshots), supplemental_signals=signals)
