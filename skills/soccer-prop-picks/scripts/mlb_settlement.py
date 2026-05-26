"""MLB settlement grading logic.

Grades picks as win/loss/push/void based on actual game results.
Handles over/under props, moneyline, run line, and void conditions
(rain-shortened, suspended, pitcher pulled early).
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class SettlementResult(str, Enum):
    WIN = "win"
    LOSS = "loss"
    PUSH = "push"
    VOID = "void"


def grade_prop(actual: float, line: float, direction: str) -> SettlementResult:
    if actual > line:
        return SettlementResult.WIN if direction == "over" else SettlementResult.LOSS
    elif actual < line:
        return SettlementResult.WIN if direction == "under" else SettlementResult.LOSS
    else:
        return SettlementResult.PUSH


def grade_moneyline(team_won: bool) -> SettlementResult:
    return SettlementResult.WIN if team_won else SettlementResult.LOSS


def grade_run_line(margin: int, spread: float) -> SettlementResult:
    adjusted = margin + spread
    if adjusted > 0:
        return SettlementResult.WIN
    elif adjusted < 0:
        return SettlementResult.LOSS
    else:
        return SettlementResult.PUSH


def grade_game_outcomes(
    *,
    picks: list[dict[str, Any]],
    actuals: dict[str, dict[str, Any]],
    game_status: str = "final",
    innings_played: int | None = None,
    pitcher_voided: set[str] | None = None,
) -> list[dict[str, Any]]:
    pitcher_voided = pitcher_voided or set()
    results: list[dict[str, Any]] = []

    for pick in picks:
        player = pick["player"]
        market = pick["market"]
        direction = pick.get("direction", "over")
        line = pick["line"]

        if _is_game_void(game_status, innings_played):
            results.append(_make_result(pick, SettlementResult.VOID))
            continue

        if game_status == "suspended":
            results.append(_make_result(pick, SettlementResult.VOID))
            continue

        if market == "pitcher_outs" and player in pitcher_voided:
            results.append(_make_result(pick, SettlementResult.VOID))
            continue

        player_actuals = actuals.get(player)
        if player_actuals is None:
            results.append(_make_result(pick, SettlementResult.VOID))
            continue

        actual_value = player_actuals.get(market)
        if actual_value is None:
            results.append(_make_result(pick, SettlementResult.VOID))
            continue

        result = grade_prop(actual=actual_value, line=line, direction=direction)
        results.append(_make_result(pick, result))

    return results


def _is_game_void(game_status: str, innings_played: int | None) -> bool:
    if game_status == "rain_shortened" and innings_played is not None:
        return innings_played < 5
    return False


def _make_result(pick: dict[str, Any], result: SettlementResult) -> dict[str, Any]:
    return {
        "player": pick["player"],
        "market": pick["market"],
        "direction": pick.get("direction", "over"),
        "line": pick["line"],
        "result": result,
    }
