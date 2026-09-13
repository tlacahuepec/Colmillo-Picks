#!/usr/bin/env python3
"""Run the bounded cross-sport reliability sample for issue #250.

The audit executes each selected fixture once and writes a compact JSON record.
It never writes credentials or provider payloads.  MLB enrichment is disabled so
the audit can report the StatsAPI/market-line boundary instead of masking it
with additional LLM calls.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
SPORT_SCRIPTS = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts"
if str(SPORT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SPORT_SCRIPTS))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from dependency_bundle import build_dependency_bundle  # noqa: E402
from mlb_statsapi_adapter import StatsAPIConfig, StatsAPIScheduleAdapter  # noqa: E402
from pick_request import PickRequest  # noqa: E402
from pipeline_runner import PipelineRunner  # noqa: E402
from pipeline_service import run_pipeline_with_payload  # noqa: E402
from sport_module import get_sport_module  # noqa: E402


@dataclass(frozen=True)
class Fixture:
    sport: str
    home_team: str
    away_team: str
    event_date: str
    league: str


_NBA_FIXTURES = (
    Fixture("basketball", "Oklahoma City Thunder", "Indiana Pacers", "2025-06-05", "nba"),
    Fixture("basketball", "Oklahoma City Thunder", "Indiana Pacers", "2025-06-08", "nba"),
    Fixture("basketball", "Indiana Pacers", "Oklahoma City Thunder", "2025-06-11", "nba"),
    Fixture("basketball", "Indiana Pacers", "Oklahoma City Thunder", "2025-06-13", "nba"),
    Fixture("basketball", "Oklahoma City Thunder", "Indiana Pacers", "2025-06-16", "nba"),
    Fixture("basketball", "Indiana Pacers", "Oklahoma City Thunder", "2025-06-19", "nba"),
    Fixture("basketball", "Oklahoma City Thunder", "Indiana Pacers", "2025-06-22", "nba"),
    Fixture("basketball", "New York Knicks", "Indiana Pacers", "2025-05-21", "nba"),
    Fixture("basketball", "New York Knicks", "Indiana Pacers", "2025-05-23", "nba"),
    Fixture("basketball", "Indiana Pacers", "New York Knicks", "2025-05-25", "nba"),
)

_SOCCER_FIXTURES = (
    Fixture("soccer", "Arsenal", "Paris Saint-Germain", "2025-04-29", "champions_league"),
    Fixture("soccer", "Paris Saint-Germain", "Arsenal", "2025-05-07", "champions_league"),
    Fixture("soccer", "Barcelona", "Inter Milan", "2025-04-30", "champions_league"),
    Fixture("soccer", "Inter Milan", "Barcelona", "2025-05-06", "champions_league"),
    Fixture("soccer", "Paris Saint-Germain", "Inter Milan", "2025-05-31", "champions_league"),
    Fixture("soccer", "Real Madrid", "Barcelona", "2025-05-11", "la_liga"),
    Fixture("soccer", "Manchester City", "Bournemouth", "2025-05-20", "premier_league"),
    Fixture("soccer", "Liverpool", "Crystal Palace", "2025-05-25", "premier_league"),
    Fixture("soccer", "Tottenham Hotspur", "Brighton and Hove Albion", "2025-05-25", "premier_league"),
    Fixture("soccer", "Nottingham Forest", "Chelsea", "2025-05-25", "premier_league"),
)


def _mlb_fixtures(*, event_date: str, sample_size: int) -> tuple[Fixture, ...]:
    """Select real MLB games from the official schedule in its published order."""
    schedule = StatsAPIScheduleAdapter(config=StatsAPIConfig(max_retries=0)).get_schedule(date=event_date)
    if not schedule.meta.available:
        raise RuntimeError(f"MLB schedule unavailable for {event_date}: {schedule.meta.error_message}")
    fixtures = []
    for game in schedule.games:
        teams = game.get("teams", {})
        home = teams.get("home", {}).get("team", {}).get("name")
        away = teams.get("away", {}).get("team", {}).get("name")
        if home and away:
            fixtures.append(Fixture("baseball", home, away, event_date, "mlb"))
        if len(fixtures) == sample_size:
            break
    if len(fixtures) < sample_size:
        raise RuntimeError(f"Only {len(fixtures)} MLB games available for {event_date}; need {sample_size}.")
    return tuple(fixtures)


def _confidence_counts(scores: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    for score in scores:
        band = str(score.get("confidence", "unknown")).lower()
        counts[band if band in counts else "unknown"] += 1
    return counts


def _summary(match_inputs: dict[str, Any], scores: list[dict[str, Any]]) -> dict[str, Any]:
    quality = match_inputs.get("data_quality", {})
    lines = match_inputs.get("lines", {})
    line_count = sum(len(value) for value in lines.values() if isinstance(value, dict)) if isinstance(lines, dict) else 0
    score_values = [float(s["score"]) for s in scores if isinstance(s.get("score"), int | float)]
    return {
        "player_count": len(match_inputs.get("players", [])),
        "prop_line_count": line_count,
        "data_quality": quality if isinstance(quality, dict) else {},
        "pick_count": len(scores),
        "confidence_counts": _confidence_counts(scores),
        "score_spread": round(max(score_values) - min(score_values), 4) if score_values else None,
    }


def _module_run(fixture: Fixture, module: Any) -> dict[str, Any]:
    request = PickRequest(
        sport=fixture.sport,
        event_date=fixture.event_date,
        home_team=fixture.home_team,
        away_team=fixture.away_team,
        markets=(),
        top_n=5,
        league=fixture.league,
    )
    runner = PipelineRunner()
    result = runner.run(request=request, module=module)
    return {"status": "success" if result.scores else "no_picks", "steps": result.steps, **_summary(result.match_inputs, result.scores)}


def _soccer_run(fixture: Fixture) -> dict[str, Any]:
    deps = build_dependency_bundle(
        use_llm=False,
        llm_provider=None,
        llm_model=None,
        allow_deterministic_fallback=False,
        league=fixture.league,
        fixture_provider_name="llm",
        availability_provider="none",
    )
    request = {
        "match_query": f"{fixture.home_team} - {fixture.away_team} {fixture.event_date}",
        "top_n": 5,
        "use_llm": False,
        "competition": fixture.league,
    }
    result = run_pipeline_with_payload(request, deps)
    status = "partial" if any(step["status"] == "failed" for step in result["steps"]) else ("success" if result["scores"] else "no_picks")
    return {"status": status, "steps": result["steps"], **_summary(result["match_inputs"], result["scores"])}


def _failure(exc: Exception) -> dict[str, Any]:
    return {
        "status": "failed",
        "error_stage": getattr(exc, "stage", "unknown"),
        "error_reason": getattr(exc, "reason", None),
        "error_type": type(exc).__name__,
    }


def run_audit(
    *, sample_size: int, mlb_date: str, on_record: Callable[[dict[str, Any]], None] | None = None
) -> dict[str, Any]:
    """Execute one bounded attempt for every selected fixture."""
    fixtures_by_sport = {
        "baseball": _mlb_fixtures(event_date=mlb_date, sample_size=sample_size),
        "basketball": _NBA_FIXTURES[:sample_size],
        "soccer": _SOCCER_FIXTURES[:sample_size],
    }
    records: list[dict[str, Any]] = []
    baseball = get_sport_module("baseball")
    # StatsAPI has no betting-line endpoint. Do not spend LLM calls masking that fact.
    baseball._enrichment_provider = None
    basketball = get_sport_module("basketball")

    for sport, fixtures in fixtures_by_sport.items():
        for fixture in fixtures:
            started = perf_counter()
            try:
                outcome = _soccer_run(fixture) if sport == "soccer" else _module_run(
                    fixture, baseball if sport == "baseball" else basketball
                )
            except Exception as exc:  # Continue the sample after any provider/runtime failure.
                outcome = _failure(exc)
            outcome["duration_ms"] = round((perf_counter() - started) * 1000)
            outcome["fixture"] = asdict(fixture)
            records.append(outcome)
            if on_record is not None:
                on_record(outcome)

    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sample_size_per_sport": sample_size,
        "mlb_schedule_date": mlb_date,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded cross-sport reliability audit.")
    parser.add_argument("--sample-size", type=int, default=10, choices=range(1, 11))
    parser.add_argument("--mlb-date", default="2025-05-24")
    parser.add_argument("--output", type=Path, required=True, help="JSON destination for metadata-only audit output.")
    args = parser.parse_args()
    partial_report: dict[str, Any] = {
        "generated_at_utc": None,
        "sample_size_per_sport": args.sample_size,
        "mlb_schedule_date": args.mlb_date,
        "records": [],
    }

    def checkpoint(record: dict[str, Any]) -> None:
        partial_report["records"].append(record)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(partial_report, indent=2) + "\n", encoding="utf-8")

    report = run_audit(sample_size=args.sample_size, mlb_date=args.mlb_date, on_record=checkpoint)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(report['records'])} records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
