"""Gemini-backed missing input enrichment helpers.

The sport modules own their required-field rules. This module provides the
LLM adapter plus deterministic merge/provenance helpers used after a sport
module decides that official inputs are incomplete.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from enrichment_selection import EnrichmentCandidate, select_best_enrichment
from llm.client import LLMClient

logger = logging.getLogger(__name__)


class MissingInputEnrichmentError(RuntimeError):
    """Raised when enrichment cannot return usable structured data."""


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GeminiMissingInputEnrichmentProvider:
    """Request only missing sport inputs from a search-grounded Gemini client."""

    provider_label = "gemini"

    def __init__(self, *, client: LLMClient, model: str | None = None) -> None:
        self._client = client
        self.model = model or "gemini"
        self.last_sources: list[Any] = []

    def enrich_missing_inputs(
        self,
        *,
        sport: str,
        home_team: str,
        away_team: str,
        match_date: str,
        league: str | None,
        requested_markets: tuple[str, ...],
        missing_fields: list[str],
        players: list[dict[str, Any]],
        lines: dict[str, Any],
        game: dict[str, Any],
        official_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        result, sources = self._single_enrichment_attempt(
            sport=sport,
            home_team=home_team,
            away_team=away_team,
            match_date=match_date,
            league=league,
            requested_markets=requested_markets,
            missing_fields=missing_fields,
            players=players,
            lines=lines,
            game=game,
            official_context=official_context,
            temperature=None,
        )
        self.last_sources = sources
        return result

    def enrich_missing_inputs_best_of_n(
        self,
        *,
        sport: str,
        home_team: str,
        away_team: str,
        match_date: str,
        league: str | None,
        requested_markets: tuple[str, ...],
        missing_fields: list[str],
        players: list[dict[str, Any]],
        lines: dict[str, Any],
        game: dict[str, Any],
        official_context: dict[str, Any] | None = None,
        n_attempts: int = 3,
        temperatures: tuple[float | None, ...] = (None, 0.7, 1.0),
        required_fields_map: dict[str, tuple[str, ...]] | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        candidates: list[EnrichmentCandidate] = []
        actual_attempts = min(n_attempts, len(temperatures))

        for i in range(actual_attempts):
            temp = temperatures[i]
            try:
                result, sources = self._single_enrichment_attempt(
                    sport=sport,
                    home_team=home_team,
                    away_team=away_team,
                    match_date=match_date,
                    league=league,
                    requested_markets=requested_markets,
                    missing_fields=missing_fields,
                    players=players,
                    lines=lines,
                    game=game,
                    official_context=official_context,
                    temperature=temp,
                )
                if result is not None:
                    candidates.append(
                        EnrichmentCandidate(attempt=i + 1, temperature=temp, result=result, sources=sources)
                    )
            except Exception as exc:
                logger.warning(
                    "best_of_n_attempt_failed attempt=%d/%d temperature=%s error=%s",
                    i + 1,
                    actual_attempts,
                    temp,
                    str(exc),
                )

        if not candidates:
            return None, {
                "strategy": "best_of_n",
                "n_attempts": actual_attempts,
                "successful_attempts": 0,
                "winner_attempt": 0,
                "winner_temperature": None,
                "selection_reason": "all_attempts_failed",
                "populated_field_count": 0,
                "avg_confidence": 0.0,
                "critical_null_count": 0,
            }

        winner, decision = select_best_enrichment(
            candidates,
            required_fields=required_fields_map,
            requested_markets=requested_markets,
        )
        self.last_sources = winner.sources
        metadata = {
            "strategy": "best_of_n",
            "n_attempts": actual_attempts,
            "successful_attempts": len(candidates),
            "winner_attempt": decision.attempt,
            "winner_temperature": decision.temperature,
            "selection_reason": decision.reason,
            "populated_field_count": decision.populated_field_count,
            "avg_confidence": decision.avg_confidence,
            "critical_null_count": decision.critical_null_count,
        }
        return winner.result, metadata

    def _single_enrichment_attempt(
        self,
        *,
        sport: str,
        home_team: str,
        away_team: str,
        match_date: str,
        league: str | None,
        requested_markets: tuple[str, ...],
        missing_fields: list[str],
        players: list[dict[str, Any]],
        lines: dict[str, Any],
        game: dict[str, Any],
        official_context: dict[str, Any] | None,
        temperature: float | None,
    ) -> tuple[dict[str, Any] | None, list[Any]]:
        result = self._client.generate_structured(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(
                sport=sport,
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                league=league,
                requested_markets=requested_markets,
                missing_fields=missing_fields,
                players=players,
                lines=lines,
                game=game,
                official_context=official_context or {},
            ),
            schema={},
            temperature=temperature,
        )
        sources = list(getattr(self._client, "last_sources", []))
        mapped = _map_enrichment_response(result, fallback_sources=sources)
        return mapped, sources

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You enrich missing sports betting-analysis inputs after official providers were tried first. "
            "Return exactly one JSON object. Use search-grounded, source-labeled data only. "
            "Never invent betting prop lines; include line source metadata for each line or leave it unknown. "
            "Use null for unverified values. Do not include markdown or prose."
        )

    @staticmethod
    def _build_user_prompt(
        *,
        sport: str,
        home_team: str,
        away_team: str,
        match_date: str,
        league: str | None,
        requested_markets: tuple[str, ...],
        missing_fields: list[str],
        players: list[dict[str, Any]],
        lines: dict[str, Any],
        game: dict[str, Any],
        official_context: dict[str, Any],
    ) -> str:
        return json.dumps(
            {
                "task": "Return only the missing inputs needed to score the requested markets.",
                "today_utc": _utc_now_z(),
                "request": {
                    "sport": sport,
                    "league": league,
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": match_date,
                    "requested_markets": list(requested_markets),
                    "missing_fields": missing_fields,
                },
                "official_inputs_already_collected": {
                    "players": players,
                    "lines": lines,
                    "game": game,
                    "context": official_context,
                },
                "required_json_shape": {
                    "confidence": "high|medium|low",
                    "retrieved_at_utc": "ISO-8601 timestamp",
                    "players": [
                        {
                            "player_name": "full name",
                            "team": "team code or official team",
                            "position": "position",
                            "type": "batter|pitcher for baseball when known",
                            "all_required_stats": "sport-specific numeric fields, null when unknown",
                            "sources": [{"label": "source name", "url": "source URL"}],
                        }
                    ],
                    "lines": {
                        "<player_name>": {
                            "<market>": {
                                "line": "numeric prop line",
                                "source": "sportsbook/source label",
                                "retrieved_at_utc": "ISO-8601 timestamp",
                                "confidence": "high|medium|low",
                                "sources": [{"source": "sportsbook", "line": 1.5, "url": "source URL"}],
                            }
                        }
                    },
                    "game": {"optional": "missing game-level context"},
                    "sources": [{"label": "source label", "url": "source URL"}],
                },
                "rules": [
                    "Return fields only when you can verify them from a source.",
                    "Every prop line must include source or sources metadata.",
                    "Do not fabricate PrizePicks, sportsbook, lineup, injury, or stat values.",
                    "If required data cannot be verified, leave it absent or null.",
                ],
            },
            sort_keys=True,
            default=str,
        )


def merge_enriched_inputs(match_inputs: dict[str, Any], enrichment: dict[str, Any]) -> None:
    """Merge enriched players/lines into match inputs and record provenance."""

    retrieved_at = enrichment.get("retrieved_at_utc")
    confidence = enrichment.get("confidence")
    sources = _normalize_sources(enrichment.get("sources", []))

    provenance = match_inputs.setdefault("input_provenance", {})
    player_provenance = provenance.setdefault("players", {})
    line_provenance = provenance.setdefault("lines", {})
    all_sources = provenance.setdefault("sources", [])
    all_sources.extend(_dedupe_sources(sources, existing=all_sources))

    existing_players = match_inputs.setdefault("players", [])
    if not isinstance(existing_players, list):
        existing_players = []
        match_inputs["players"] = existing_players
    by_name = {
        str(player.get("player_name", "")).strip(): player
        for player in existing_players
        if isinstance(player, dict) and str(player.get("player_name", "")).strip()
    }

    for player in enrichment.get("players", []) or []:
        if not isinstance(player, dict):
            continue
        name = str(player.get("player_name", "")).strip()
        if not name:
            continue
        cleaned = {k: v for k, v in player.items() if v is not None}
        cleaned.setdefault("input_source", "gemini_enriched")
        target = by_name.get(name)
        if target is None:
            existing_players.append(cleaned)
            by_name[name] = cleaned
        else:
            for key, value in cleaned.items():
                if value is not None:
                    target[key] = value
        player_provenance[name] = {
            "source": "gemini_enriched",
            "provider": "gemini",
            "confidence": cleaned.get("confidence") or confidence,
            "retrieved_at_utc": cleaned.get("retrieved_at_utc") or retrieved_at,
            "sources": _normalize_sources(cleaned.get("sources", [])) or sources,
        }

    existing_lines = match_inputs.setdefault("lines", {})
    if not isinstance(existing_lines, dict):
        existing_lines = {}
        match_inputs["lines"] = existing_lines

    for player_name, markets in (enrichment.get("lines", {}) or {}).items():
        if not isinstance(markets, dict):
            continue
        player_key = str(player_name)
        player_lines = existing_lines.setdefault(player_key, {})
        if not isinstance(player_lines, dict):
            player_lines = {}
            existing_lines[player_key] = player_lines
        for market, raw_line in markets.items():
            normalized = _normalize_line(raw_line, retrieved_at=retrieved_at, confidence=confidence)
            if normalized is None:
                continue
            player_lines[str(market)] = normalized
            line_provenance[f"{player_key}:{market}"] = {
                "source": "gemini_enriched",
                "provider": "gemini",
                "confidence": normalized.get("confidence") or confidence,
                "retrieved_at_utc": normalized.get("retrieved_at_utc") or retrieved_at,
                "sources": _normalize_sources(normalized.get("sources", [])) or sources,
            }

    if isinstance(enrichment.get("game"), dict):
        game = match_inputs.setdefault("game", {})
        if isinstance(game, dict):
            for key, value in enrichment["game"].items():
                if value is not None:
                    game[key] = value

    data_quality = match_inputs.setdefault("data_quality", {})
    if isinstance(data_quality, dict):
        data_quality.update(
            {
                "enrichment_status": "success",
                "enrichment_source": "gemini",
                "enrichment_confidence": confidence or "unknown",
                "enrichment_retrieved_at_utc": retrieved_at,
            }
        )

    summary = match_inputs.setdefault("collection_summary", {})
    if isinstance(summary, dict):
        summary["enrichment_status"] = "success"
        summary["enrichment_source"] = "gemini"


def mark_enrichment_failed(
    match_inputs: dict[str, Any],
    *,
    reason: str,
    missing_fields: list[str],
) -> None:
    data_quality = match_inputs.setdefault("data_quality", {})
    if isinstance(data_quality, dict):
        data_quality.update(
            {
                "enrichment_status": "failed",
                "enrichment_source": "gemini",
                "enrichment_failure_reason": reason,
                "enrichment_missing_fields": list(missing_fields),
            }
        )
    summary = match_inputs.setdefault("collection_summary", {})
    if isinstance(summary, dict):
        summary["enrichment_status"] = "failed"
        summary["enrichment_failure_reason"] = reason


def pick_input_provenance(match_inputs: dict[str, Any], *, player: str, market: str) -> dict[str, Any]:
    provenance = match_inputs.get("input_provenance", {})
    if not isinstance(provenance, dict):
        return {}
    players = provenance.get("players", {})
    lines = provenance.get("lines", {})
    return {
        "player": players.get(player, {"source": "official"}) if isinstance(players, dict) else {"source": "official"},
        "line": lines.get(f"{player}:{market}", {"source": "official"}) if isinstance(lines, dict) else {"source": "official"},
    }


def _map_enrichment_response(result: dict[str, Any], *, fallback_sources: list[Any]) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        raise MissingInputEnrichmentError("Enrichment returned non-object JSON.")

    sources = _normalize_sources(result.get("sources", []))
    if not sources:
        sources = _normalize_sources(fallback_sources)

    enrichment = {
        "players": result.get("players") if isinstance(result.get("players"), list) else [],
        "lines": _normalize_lines_object(result.get("lines", {})),
        "game": result.get("game") if isinstance(result.get("game"), dict) else {},
        "retrieved_at_utc": result.get("retrieved_at_utc") or _utc_now_z(),
        "confidence": result.get("confidence") or "unknown",
        "sources": sources,
    }
    if not enrichment["players"] and not enrichment["lines"] and not enrichment["game"]:
        return None
    return enrichment


def _normalize_lines_object(raw_lines: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw_lines, list):
        mapped: dict[str, dict[str, Any]] = {}
        for entry in raw_lines:
            if not isinstance(entry, dict):
                continue
            player = str(entry.get("player_name", "")).strip()
            market = str(entry.get("market", "")).strip()
            if not player or not market:
                continue
            mapped.setdefault(player, {})[market] = entry
        return mapped
    if isinstance(raw_lines, dict):
        return raw_lines
    return {}


def _normalize_line(raw_line: Any, *, retrieved_at: str | None, confidence: str | None) -> dict[str, Any] | None:
    if isinstance(raw_line, dict):
        line_value = _safe_float(raw_line.get("line"))
        if line_value is None or not _has_line_source_metadata(raw_line):
            return None
        normalized = dict(raw_line)
        normalized["line"] = line_value
        normalized.setdefault("input_source", "gemini_enriched")
        normalized.setdefault("retrieved_at_utc", retrieved_at)
        normalized.setdefault("confidence", confidence or "unknown")
        return normalized
    return None


def _has_line_source_metadata(line_data: dict[str, Any]) -> bool:
    source = str(line_data.get("source", "")).strip()
    sources = line_data.get("sources")
    return bool(source or (isinstance(sources, list) and sources))


def _normalize_sources(raw_sources: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    if not isinstance(raw_sources, list):
        return normalized
    for source in raw_sources:
        if isinstance(source, dict):
            label = str(source.get("label") or source.get("source") or source.get("title") or "").strip()
            url = source.get("url")
        else:
            label = str(getattr(source, "title", "") or getattr(source, "url", "")).strip()
            url = getattr(source, "url", None)
        if label or url:
            normalized.append({"label": label or str(url), "url": url})
    return normalized


def _dedupe_sources(
    new_sources: list[dict[str, Any]], *, existing: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    seen = {(src.get("label"), src.get("url")) for src in existing if isinstance(src, dict)}
    deduped: list[dict[str, Any]] = []
    for source in new_sources:
        key = (source.get("label"), source.get("url"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
