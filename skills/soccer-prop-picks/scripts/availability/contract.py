from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Protocol, TypedDict

AvailabilityStatus = Literal["available", "unavailable", "unknown"]


class AvailabilityEntry(TypedDict):
    prizepicks: AvailabilityStatus
    alternatives: dict[str, AvailabilityStatus]
    retrieved_at_utc: str
    fallback_reason: str
    final_status: AvailabilityStatus


class AvailabilityPayload(TypedDict):
    fallback_mode: bool
    fallback_reason: str
    picks: dict[str, AvailabilityEntry]


class AvailabilityAdapter(Protocol):
    def check_picks(self, picks: list[dict[str, str]]) -> AvailabilityPayload:
        """Return normalized platform availability keyed by '<player_id>:<market>'."""


def now_utc_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_status(value: object) -> AvailabilityStatus:
    status = str(value).strip().lower()
    if status in {"available", "unavailable", "unknown"}:
        return status
    return "unknown"


def resolve_final_availability(prizepicks: AvailabilityStatus, alternatives: list[AvailabilityStatus]) -> AvailabilityStatus:
    statuses = [prizepicks] + alternatives
    if any(status == "available" for status in statuses):
        return "available"
    if statuses and all(status == "unavailable" for status in statuses):
        return "unavailable"
    return "unknown"


def standardize_availability_entry(
    raw_entry: dict[str, object],
    *,
    default_retrieved_at_utc: str,
    fallback_reason: str,
) -> AvailabilityEntry:
    prizepicks_status = _normalize_status(raw_entry.get("prizepicks"))
    raw_alternatives = raw_entry.get("alternatives")
    alternatives = {
        str(name): _normalize_status(status)
        for name, status in (raw_alternatives.items() if isinstance(raw_alternatives, dict) else [])
    }
    retrieved_at_utc = str(raw_entry.get("retrieved_at_utc") or default_retrieved_at_utc)
    resolved_final = resolve_final_availability(prizepicks_status, list(alternatives.values()))
    final_status = _normalize_status(raw_entry.get("final_status")) if raw_entry.get("final_status") else resolved_final

    return {
        "prizepicks": prizepicks_status,
        "alternatives": alternatives,
        "retrieved_at_utc": retrieved_at_utc,
        "fallback_reason": str(raw_entry.get("fallback_reason") or fallback_reason),
        "final_status": final_status,
    }


def standardize_availability_payload(raw_payload: dict[str, object], *, pick_keys: list[str]) -> AvailabilityPayload:
    fallback_reason = str(raw_payload.get("fallback_reason") or "data fetch ok")
    fallback_mode = bool(raw_payload.get("fallback_mode", False))
    picks_raw = raw_payload.get("picks")
    picks_map = picks_raw if isinstance(picks_raw, dict) else {}
    default_retrieved_at_utc = now_utc_z()

    picks: dict[str, AvailabilityEntry] = {}
    for key in pick_keys:
        raw_entry = picks_map.get(key)
        safe_entry = raw_entry if isinstance(raw_entry, dict) else {}
        picks[key] = standardize_availability_entry(
            safe_entry,
            default_retrieved_at_utc=default_retrieved_at_utc,
            fallback_reason=fallback_reason,
        )

    return {
        "fallback_mode": fallback_mode,
        "fallback_reason": fallback_reason,
        "picks": picks,
    }
