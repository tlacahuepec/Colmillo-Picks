"""Normalization helpers for collect_match_inputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def normalize_team_name(team_name: str) -> str:
    tokens = [token for token in team_name.strip().split() if token]
    return " ".join(token.capitalize() for token in tokens) if tokens else team_name.strip()


def normalize_match_date(match_date: str) -> str:
    try:
        return datetime.strptime(match_date.strip(), "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError("Match date must use YYYY-MM-DD format.") from exc


def derive_position_group(role_tag: str) -> str:
    if role_tag in {"GK"}:
        return "GK"
    if role_tag in {"CB", "LB", "RB", "LWB", "RWB"}:
        return "DEF"
    if role_tag in {"CM", "CDM", "CAM", "LM", "RM", "DM"}:
        return "MID"
    return "FWD"


def normalize_player(player: dict[str, Any], default_team_id: str) -> dict[str, Any]:
    role = player.get("role_tag") or player.get("specific_role") or "CM"
    market_lines = player.get("market_lines") or {}
    return {
        "player_id": player.get("player_id", "unknown-player"),
        "player_name": player.get("player_name", "Unknown Player"),
        "team_id": player.get("team_id", default_team_id),
        "position_group": player.get("position_group", derive_position_group(role)),
        "specific_role": player.get("specific_role", role),
        "role_tag": role,
        "expected_minutes": int(player.get("expected_minutes", 75)),
        "substitution_risk": player.get("substitution_risk", "medium"),
        "captain": bool(player.get("captain", False)),
        "is_lone_striker": bool(player.get("is_lone_striker", False)),
        "expected_passes_baseline": float(player.get("expected_passes_baseline", 25)),
        "expected_shots_baseline": float(player.get("expected_shots_baseline", 1)),
        "market_lines": {
            "passes": float(market_lines.get("passes", 20.5)),
            "shots": float(market_lines.get("shots", 1.5)),
        },
    }


def normalize_weather(weather_payload: dict[str, Any], default_timestamp: str) -> dict[str, Any]:
    return {
        "summary": weather_payload.get("summary", "Unknown"),
        "temperature_c": float(weather_payload.get("temperature_c", 15)),
        "wind_kph": float(weather_payload.get("wind_kph", 10)),
        "precipitation_probability": float(weather_payload.get("precipitation_probability", 0.2)),
        "source_timestamp_utc": weather_payload.get("source_timestamp_utc", default_timestamp),
    }


def normalize_snapshots(snapshots: list[dict[str, Any]], market_ts: str) -> list[dict[str, Any]]:
    return [
        {
            "source": snap.get("source", "unknown_book"),
            "odds_decimal": float(snap.get("odds_decimal", 2.0)),
            "captured_at_utc": snap.get("captured_at_utc", market_ts),
        }
        for snap in snapshots
    ]
