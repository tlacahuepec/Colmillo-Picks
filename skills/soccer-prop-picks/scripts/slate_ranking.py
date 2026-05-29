"""Cross-sport slate candidate normalization and ranking helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

AvailabilityStatus = Literal["available", "unavailable", "unknown"]

_NO_BET_TOKENS = {"no-bet", "no_bet", "nobet", "pass", "skip"}
_CONFIDENCE_RANK = {"high": 3, "medium": 2, "low": 1}
_AVAILABILITY_RANK = {"available": 3, "unknown": 2, "unavailable": 1}


@dataclass(frozen=True, slots=True)
class SlateCandidate:
    """Normalized pick shape used by Best Today slate ranking."""

    sport: str
    source_match: dict[str, Any]
    player: str
    market: str
    line: Any
    direction: str
    confidence: str
    raw_score: float | None
    normalized_score: float
    risk_flags: tuple[str, ...]
    availability_status: AvailabilityStatus
    source_pick: dict[str, Any]


def candidate_from_pick(
    pick: Mapping[str, Any],
    *,
    sport: str,
    source_match: Mapping[str, Any] | None = None,
    availability: Mapping[str, Any] | str | None = None,
) -> SlateCandidate | None:
    """Convert one sport-specific pick dictionary into a slate candidate.

    V1 accepts the existing scorer outputs directly. Scores in the current
    modules are 0..1, while already-normalized future values may be 0..100.
    """

    if _is_no_bet(pick):
        return None

    raw_score, normalized_score, score_flags = _normalize_score(pick.get("score"))
    return SlateCandidate(
        sport=_clean_text(sport, default="unknown"),
        source_match=dict(source_match or {}),
        player=_clean_text(pick.get("player") or pick.get("player_name"), default="Unknown Player"),
        market=_clean_text(pick.get("market"), default="unknown"),
        line=pick.get("line"),
        direction=_clean_text(pick.get("direction"), default="unknown"),
        confidence=_clean_text(pick.get("confidence"), default="unknown").lower(),
        raw_score=raw_score,
        normalized_score=normalized_score,
        risk_flags=_risk_flags(pick, extra_flags=score_flags),
        availability_status=_availability_status(pick=pick, availability=availability),
        source_pick=dict(pick),
    )


def candidates_from_picks(
    picks: Iterable[Mapping[str, Any]],
    *,
    sport: str,
    source_match: Mapping[str, Any] | None = None,
    availability_by_key: Mapping[str, Mapping[str, Any] | str] | None = None,
) -> list[SlateCandidate]:
    """Convert a batch of scorer pick dictionaries into ranked-slate inputs."""

    candidates: list[SlateCandidate] = []
    for pick in picks:
        availability = _lookup_availability(pick, availability_by_key)
        candidate = candidate_from_pick(
            pick,
            sport=sport,
            source_match=source_match,
            availability=availability,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def rank_slate_candidates(
    candidates: Iterable[SlateCandidate],
    *,
    top_n: int | None = None,
) -> list[SlateCandidate]:
    """Rank candidates with a deterministic V1 ordering.

    Order: normalized score, confidence, availability, lower risk count, then
    stable identity fields so equal candidates never depend on input order.
    """

    ranked = sorted(candidates, key=_rank_key)
    if top_n is None:
        return ranked
    return ranked[: max(0, top_n)]


def _rank_key(candidate: SlateCandidate) -> tuple[Any, ...]:
    return (
        -candidate.normalized_score,
        -_CONFIDENCE_RANK.get(candidate.confidence, 0),
        -_AVAILABILITY_RANK.get(candidate.availability_status, 0),
        len(candidate.risk_flags),
        candidate.sport,
        _source_match_id(candidate.source_match),
        candidate.player,
        candidate.market,
        str(candidate.line),
        candidate.direction,
    )


def _is_no_bet(pick: Mapping[str, Any]) -> bool:
    recommendation = _token(pick.get("recommendation"))
    direction = _token(pick.get("direction"))
    return recommendation in _NO_BET_TOKENS or direction in _NO_BET_TOKENS


def _normalize_score(raw_score: Any) -> tuple[float | None, float, list[str]]:
    flags: list[str] = []
    if raw_score is None:
        return None, 0.0, ["missing_score"]

    try:
        parsed = float(raw_score)
    except (TypeError, ValueError):
        return None, 0.0, ["invalid_score"]

    normalized = parsed * 100.0 if -1.0 <= parsed <= 1.0 else parsed
    if normalized < 0.0:
        flags.append("score_clipped_low")
        normalized = 0.0
    elif normalized > 100.0:
        flags.append("score_clipped_high")
        normalized = 100.0
    return parsed, round(normalized, 4), flags


def _risk_flags(pick: Mapping[str, Any], *, extra_flags: Iterable[str]) -> tuple[str, ...]:
    explainability = pick.get("explainability")
    raw_flags = explainability.get("risk_flags") if isinstance(explainability, Mapping) else []
    flags = [str(flag).strip() for flag in raw_flags if str(flag).strip()]
    flags.extend(flag for flag in extra_flags if flag)
    return tuple(sorted(set(flags)))


def _availability_status(
    *,
    pick: Mapping[str, Any],
    availability: Mapping[str, Any] | str | None,
) -> AvailabilityStatus:
    raw_status: Any = availability
    if raw_status is None:
        raw_status = pick.get("availability") or pick.get("availability_status")
    if isinstance(raw_status, Mapping):
        raw_status = (
            raw_status.get("final_status")
            or raw_status.get("status")
            or raw_status.get("availability_status")
            or raw_status.get("prizepicks")
        )
    status = _token(raw_status)
    if status in {"available", "unavailable", "unknown"}:
        return status  # type: ignore[return-value]
    return "unknown"


def _lookup_availability(
    pick: Mapping[str, Any],
    availability_by_key: Mapping[str, Mapping[str, Any] | str] | None,
) -> Mapping[str, Any] | str | None:
    if not availability_by_key:
        return None
    market = _clean_text(pick.get("market"), default="unknown")
    player_key = _clean_text(pick.get("player_id") or pick.get("player"), default="")
    if not player_key:
        return None
    return availability_by_key.get(f"{player_key}:{market}")


def _source_match_id(source_match: Mapping[str, Any]) -> str:
    return _clean_text(
        source_match.get("match_id") or source_match.get("id") or source_match.get("fixture"),
        default="",
    )


def _clean_text(value: Any, *, default: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text if text else default


def _token(value: Any) -> str:
    return str(value).strip().lower() if value is not None else ""
