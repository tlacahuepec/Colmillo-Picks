from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import httpx

from availability.base import AdapterRuntimeConfig, AvailabilityResult, Pick, SportsbookAvailabilityAdapter
from availability.contract import AvailabilityPayload, now_utc_z, standardize_availability_payload

_PROJECTIONS_ENDPOINT = "https://api.prizepicks.com/projections"
_DEFAULT_CACHE_TTL_SECONDS = 300
_PLAYER_MIN_MATCH_RATIO = 0.75
_LINE_TOLERANCE = 0.15


@dataclass(frozen=True)
class _Projection:
    player_name: str
    stat_type: str
    line_score: float


class PrizePicksAdapter(SportsbookAvailabilityAdapter):
    """PrizePicks adapter backed by the public projections endpoint."""

    def __init__(
        self,
        *,
        config: AdapterRuntimeConfig | None = None,
        timeout_seconds: float = 10.0,
        cache_ttl_seconds: int = _DEFAULT_CACHE_TTL_SECONDS,
        league_id: int | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(platform="prizepicks", config=config)
        self._timeout_seconds = timeout_seconds
        self._cache_ttl_seconds = cache_ttl_seconds
        self._league_id = league_id
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._cache_expires_at: datetime | None = None
        self._cached_projections: list[_Projection] = []

    def _auth_headers(self) -> dict[str, str]:
        api_key = os.getenv("PRIZEPICKS_API_KEY")
        session_token = os.getenv("PRIZEPICKS_SESSION_TOKEN")

        headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            headers["X-Api-Key"] = api_key
        elif session_token:
            headers["Authorization"] = f"Bearer {session_token}"
        return headers

    def _normalize(self, value: str) -> str:
        return "".join(ch.lower() for ch in value if ch.isalnum() or ch.isspace()).strip()

    def _line_matches(self, candidate: float, target: float) -> bool:
        return abs(candidate - target) <= _LINE_TOLERANCE

    def _player_matches(self, requested_player: str, candidate_player: str) -> bool:
        req_tokens = requested_player.split()
        cand_tokens = candidate_player.split()
        ratio = SequenceMatcher(None, requested_player, candidate_player).ratio()
        if ratio >= _PLAYER_MIN_MATCH_RATIO:
            return True
        if len(req_tokens) >= 2 and len(cand_tokens) >= 2:
            req_last = req_tokens[-1]
            cand_last = cand_tokens[-1]
            if req_last == cand_last and req_tokens[0][0:1] == cand_tokens[0][0:1]:
                return True
        return False

    def _best_projection_match(self, player: str, market: str, line: float) -> _Projection | None:
        requested_player = self._normalize(player)
        requested_market = self._normalize(market)
        best: tuple[float, _Projection] | None = None

        for projection in self._cached_projections:
            if self._normalize(projection.stat_type) != requested_market:
                continue
            if not self._line_matches(projection.line_score, line):
                continue

            normalized_candidate = self._normalize(projection.player_name)
            if not self._player_matches(requested_player, normalized_candidate):
                continue
            ratio = SequenceMatcher(None, requested_player, normalized_candidate).ratio()
            if best is None or ratio > best[0]:
                best = (ratio, projection)

        return best[1] if best else None

    def _parse_projections(self, payload: dict[str, object]) -> list[_Projection]:
        included_raw = payload.get("included")
        data_raw = payload.get("data")
        if not isinstance(included_raw, list) or not isinstance(data_raw, list):
            return []

        players: dict[str, str] = {}
        for item in included_raw:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "new_player":
                continue
            player_id = str(item.get("id") or "")
            attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
            name = str(attributes.get("name") or "")
            if player_id and name:
                players[player_id] = name

        parsed: list[_Projection] = []
        for item in data_raw:
            if not isinstance(item, dict):
                continue
            relationships = item.get("relationships") if isinstance(item.get("relationships"), dict) else {}
            player_rel = relationships.get("new_player") if isinstance(relationships.get("new_player"), dict) else {}
            player_data = player_rel.get("data") if isinstance(player_rel.get("data"), dict) else {}
            player_id = str(player_data.get("id") or "")
            player_name = players.get(player_id)
            if not player_name:
                continue

            attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
            stat_type = str(attrs.get("stat_type") or "")
            line_score = attrs.get("line_score")
            if not stat_type or not isinstance(line_score, (float, int)):
                continue
            parsed.append(_Projection(player_name=player_name, stat_type=stat_type, line_score=float(line_score)))

        return parsed

    def _refresh_cache(self) -> None:
        params: dict[str, object] = {"per_page": 250, "single_stat": "true"}
        if self._league_id is not None:
            params["league_id"] = self._league_id

        response = self._client.get(_PROJECTIONS_ENDPOINT, params=params, headers=self._auth_headers())
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("invalid PrizePicks projections payload")

        self._cached_projections = self._parse_projections(payload)
        self._cache_expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._cache_ttl_seconds)

    def _ensure_cache(self) -> None:
        if self._cache_expires_at and datetime.now(timezone.utc) < self._cache_expires_at:
            return
        self._refresh_cache()

    def check_availability(self, player: str, market: str, line: float) -> AvailabilityResult:
        now = datetime.now(timezone.utc)
        try:
            self._ensure_cache()
            matched = self._best_projection_match(player, market, line)
            return AvailabilityResult(
                available=matched is not None,
                platform=self.platform,
                odds=None,
                url=_PROJECTIONS_ENDPOINT,
                last_checked=now,
            )
        except Exception:
            return AvailabilityResult(available=False, platform=self.platform, odds=None, url=None, last_checked=now)

    def check_batch(self, picks: list[Pick]) -> list[AvailabilityResult]:
        return super().check_batch(picks)

    def check_picks(self, picks: list[dict[str, str]]) -> AvailabilityPayload:
        pick_keys = [f"{pick.get('player_id', 'unknown')}:{pick.get('market', 'unknown')}" for pick in picks]
        now_iso = now_utc_z()
        mapped: dict[str, dict[str, object]] = {}
        fallback_mode = False
        fallback_reason = "data fetch ok"

        for idx, pick in enumerate(picks):
            key = pick_keys[idx]
            player = str(pick.get("player_name") or pick.get("player_id") or "")
            market = str(pick.get("market") or "")
            line = float(pick.get("line") or 0.0)
            result = self.check_availability(player=player, market=market, line=line)

            if result.url is None:
                fallback_mode = True
                fallback_reason = "platform_down"
                status = "unknown"
            else:
                status = "available" if result.available else "unavailable"

            mapped[key] = {
                "prizepicks": status,
                "alternatives": {},
                "retrieved_at_utc": now_iso,
                "fallback_reason": fallback_reason,
            }

        return standardize_availability_payload(
            {"fallback_mode": fallback_mode, "fallback_reason": fallback_reason, "picks": mapped},
            pick_keys=pick_keys,
        )
