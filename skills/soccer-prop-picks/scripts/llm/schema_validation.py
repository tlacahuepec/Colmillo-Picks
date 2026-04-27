from __future__ import annotations

from typing import Any

_REQUIRED_FIELDS = {
    "player_id",
    "market_type",
    "recommended_side",
    "confidence_band",
    "rationale",
    "risk_flags",
}
_ALLOWED_SIDES = {"over", "under"}
_ALLOWED_CONFIDENCE_BANDS = {"low", "medium", "high"}


def _normalize_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string")
    return normalized


def validate_llm_payload(payload: dict) -> dict:
    """Validate and normalize a model-generated pick explanation payload."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dictionary")

    missing = sorted(_REQUIRED_FIELDS - payload.keys())
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    normalized: dict[str, Any] = {
        "player_id": _normalize_string(payload.get("player_id"), "player_id"),
        "market_type": _normalize_string(payload.get("market_type"), "market_type"),
        "rationale": _normalize_string(payload.get("rationale"), "rationale"),
    }

    recommended_side = _normalize_string(payload.get("recommended_side"), "recommended_side").lower()
    if recommended_side not in _ALLOWED_SIDES:
        allowed = ", ".join(sorted(_ALLOWED_SIDES))
        raise ValueError(f"recommended_side must be one of: {allowed}")
    normalized["recommended_side"] = recommended_side

    confidence_band = _normalize_string(payload.get("confidence_band"), "confidence_band").lower()
    if confidence_band not in _ALLOWED_CONFIDENCE_BANDS:
        allowed = ", ".join(sorted(_ALLOWED_CONFIDENCE_BANDS))
        raise ValueError(f"confidence_band must be one of: {allowed}")
    normalized["confidence_band"] = confidence_band

    risk_flags = payload.get("risk_flags")
    if not isinstance(risk_flags, list):
        raise ValueError("risk_flags must be an array of strings")

    normalized_flags: list[str] = []
    for flag in risk_flags:
        if not isinstance(flag, str):
            raise ValueError("risk_flags must contain only strings")
        stripped = flag.strip()
        if stripped:
            normalized_flags.append(stripped)
    normalized["risk_flags"] = normalized_flags

    return normalized
