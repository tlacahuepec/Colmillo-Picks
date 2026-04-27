from __future__ import annotations

from tests.conftest import load_script_module


def test_normalize_player_applies_defaults() -> None:
    normalizers = load_script_module("normalizers.py")

    normalized = normalizers.normalize_player({}, default_team_id="ABC")

    assert normalized["player_id"] == "unknown-player"
    assert normalized["team_id"] == "ABC"
    assert normalized["position_group"] == "MID"
    assert normalized["expected_minutes"] == 75
    assert normalized["market_lines"] == {"passes": 20.5, "shots": 1.5}


def test_normalize_player_prefers_explicit_role_and_position_group() -> None:
    normalizers = load_script_module("normalizers.py")

    normalized = normalizers.normalize_player(
        {"specific_role": "RB", "position_group": "DEF", "market_lines": {"passes": 30}},
        default_team_id="ABC",
    )

    assert normalized["role_tag"] == "RB"
    assert normalized["specific_role"] == "RB"
    assert normalized["position_group"] == "DEF"
    assert normalized["market_lines"]["passes"] == 30.0
    assert normalized["market_lines"]["shots"] == 1.5


def test_build_validation_rejects_on_critical_fields() -> None:
    resolution = load_script_module("provider_resolution.py")
    context = resolution.ResolutionContext(
        critical_missing_fields=["teams.projected_lineup", "players", "market.sportsbook_snapshots"],
        notes=["a note"],
    )

    validation = resolution.build_validation(context)

    assert validation["should_reject_prediction"] is True
    assert validation["critical_missing_fields"] == [
        "market.sportsbook_snapshots",
        "players",
        "teams.projected_lineup",
    ]


def test_build_validation_keeps_prediction_when_non_rejecting_fields_missing() -> None:
    resolution = load_script_module("provider_resolution.py")
    context = resolution.ResolutionContext(critical_missing_fields=["match.weather"], notes=[])

    validation = resolution.build_validation(context)

    assert validation["should_reject_prediction"] is False
    assert validation["notes"] == "All required providers returned data."
