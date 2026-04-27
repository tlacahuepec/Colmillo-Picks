from __future__ import annotations

from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts"


def load_script_module(script_name: str):
    path = SKILL_SCRIPTS / script_name
    spec = spec_from_file_location(path.stem.replace("-", "_"), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sample_match_inputs() -> dict[str, Any]:
    ts = _now_utc_z()
    return {
        "schema_version": "v1.1.0",
        "match_id": "EPL-ARS-LIV-2026-04-27",
        "competition": "Premier League",
        "match": {
            "match_id": "EPL-ARS-LIV-2026-04-27",
            "competition_type": "league",
            "is_elimination": False,
            "overtime_possible": False,
            "kickoff_utc": ts,
            "venue": {"name": "Emirates Stadium", "city": "London", "country": "England"},
            "weather": {
                "summary": "Partly cloudy",
                "temperature_c": 15,
                "wind_kph": 12,
                "precipitation_probability": 0.15,
                "source_timestamp_utc": ts,
            },
        },
        "teams": [
            {
                "team_id": "ARS",
                "team_name": "Arsenal",
                "home_away": "home",
                "projected_lineup": {
                    "status": "confirmed",
                    "formation": "4-3-3",
                    "starters": ["Player A", "Player B"],
                    "source_timestamp_utc": ts,
                },
                "injuries": [{"player_name": "Injured A", "reason": "hamstring", "status": "out"}],
                "suspensions": [],
                "possession_profile": {"avg_possession_pct": 58, "style_tag": "high_possession"},
                "standings_context": {
                    "table_position": 2,
                    "points": 73,
                    "games_played": 33,
                    "motivation_tag": "title_race",
                },
            },
            {
                "team_id": "LIV",
                "team_name": "Liverpool",
                "home_away": "away",
                "projected_lineup": {
                    "status": "confirmed",
                    "formation": "4-3-3",
                    "starters": ["Player C", "Player D"],
                    "source_timestamp_utc": ts,
                },
                "injuries": [],
                "suspensions": [{"player_name": "Suspended B", "reason": "red_card", "status": "suspended"}],
                "possession_profile": {"avg_possession_pct": 54, "style_tag": "high_possession"},
                "standings_context": {
                    "table_position": 3,
                    "points": 70,
                    "games_played": 33,
                    "motivation_tag": "europe_race",
                },
            },
        ],
        "market": {
            "source_timestamp_utc": ts,
            "sportsbook_snapshots": [
                {"source": "book1", "odds_decimal": 1.85},
                {"source": "book2", "odds_decimal": 1.87},
                {"source": "book3", "odds_decimal": 1.84},
                {"source": "book4", "odds_decimal": 1.88},
                {"source": "book5", "odds_decimal": 1.86},
            ],
        },
        "players": [
            {
                "player_id": "ars-8",
                "player_name": "Arsenal CM",
                "team_id": "ARS",
                "position_group": "MID",
                "specific_role": "CM",
                "role_tag": "CM",
                "expected_minutes": 88,
                "substitution_risk": "low",
                "captain": True,
                "is_lone_striker": False,
                "expected_passes_baseline": 67,
                "expected_shots_baseline": 1.2,
                "market_lines": {"passes": 61.5, "shots": 1.5},
            },
            {
                "player_id": "ars-9",
                "player_name": "Arsenal ST",
                "team_id": "ARS",
                "position_group": "FWD",
                "specific_role": "ST",
                "role_tag": "ST",
                "expected_minutes": 86,
                "substitution_risk": "medium",
                "is_lone_striker": True,
                "expected_passes_baseline": 24,
                "expected_shots_baseline": 3.6,
                "market_lines": {"passes": 22.5, "shots": 2.5},
            },
            {
                "player_id": "liv-4",
                "player_name": "Liverpool CB",
                "team_id": "LIV",
                "position_group": "DEF",
                "specific_role": "CB",
                "role_tag": "CB",
                "expected_minutes": 90,
                "substitution_risk": "low",
                "is_lone_striker": False,
                "expected_passes_baseline": 72,
                "expected_shots_baseline": 0.4,
                "market_lines": {"passes": 64.5, "shots": 0.5},
            },
        ],
        "validation": {"critical_missing_fields": [], "should_reject_prediction": False},
    }
