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


def test_resolve_fixture_records_failure_status_and_fallback_on_exception() -> None:
    resolution = load_script_module("provider_resolution.py")

    class _BrokenFixtureProvider:
        def lookup_fixture(self, request):
            raise RuntimeError("fixture timeout")

    context = resolution.ResolutionContext()
    request = type("Req", (), {})()

    fixture = resolution.resolve_fixture(
        request=request,
        fixture_provider=_BrokenFixtureProvider(),
        fallback_fixture_fn=lambda req: {"match_id": "fallback"},
        context=context,
    )

    assert fixture["match_id"] == "fallback"
    assert context.provider_status["fixture"]["attempted"] is True
    assert context.provider_status["fixture"]["success"] is False
    assert context.provider_status["fixture"]["fallback_used"] is True
    assert context.provider_status["fixture"]["error_summary"] == "fixture timeout"


def test_provider_resolution_error_accepts_optional_context_for_observability() -> None:
    """Covers ProviderResolutionError.__init__ signature (incl. the forward-ref
    context: "ResolutionContext" | None) and attachment of rich context for
    Epic #219 cross-sport failure observability. This test would have caught
    the annotation evaluation TypeError on import.
    """
    resolution = load_script_module("provider_resolution.py")

    err_no_ctx = resolution.ProviderResolutionError("no context provided")
    assert err_no_ctx.context is None
    assert str(err_no_ctx) == "no context provided"

    ctx = resolution.ResolutionContext(
        critical_missing_fields=["players"],
        notes=["unit test context"],
    )
    err_with_ctx = resolution.ProviderResolutionError("with context", context=ctx)
    assert err_with_ctx.context is ctx
    assert err_with_ctx.context.critical_missing_fields == ["players"]
