from __future__ import annotations

from availability.base import AdapterRuntimeConfig, Pick
from availability.contract import resolve_final_availability, standardize_availability_entry
from availability.mock_adapter import DeterministicMockAvailabilityAdapter


def test_resolve_final_availability_available_when_any_platform_available() -> None:
    assert resolve_final_availability("unknown", ["unavailable", "available"]) == "available"


def test_resolve_final_availability_unavailable_when_all_platforms_unavailable() -> None:
    assert resolve_final_availability("unavailable", ["unavailable", "unavailable"]) == "unavailable"


def test_resolve_final_availability_unknown_when_mixed_without_available() -> None:
    assert resolve_final_availability("unknown", ["unavailable"]) == "unknown"


def test_standardize_entry_defaults_to_unknown_values() -> None:
    standardized = standardize_availability_entry(
        {},
        default_retrieved_at_utc="2026-04-27T12:00:00Z",
        fallback_reason="partial_data",
    )

    assert standardized["prizepicks"] == "unknown"
    assert standardized["alternatives"] == {}
    assert standardized["retrieved_at_utc"] == "2026-04-27T12:00:00Z"
    assert standardized["fallback_reason"] == "partial_data"
    assert standardized["final_status"] == "unknown"


def test_deterministic_mock_adapter_returns_standardized_fields() -> None:
    adapter = DeterministicMockAvailabilityAdapter(
        seed_data={
            "ars-8:passes": {
                "prizepicks": "unknown",
                "alternatives": {"Underdog": "available"},
                "retrieved_at_utc": "2026-04-27T12:00:00Z",
            }
        },
        fallback_reason="mock_seed",
    )

    result = adapter.check_picks([{"player_id": "ars-8", "market": "passes"}])
    entry = result["picks"]["ars-8:passes"]

    assert entry["prizepicks"] == "unknown"
    assert entry["alternatives"] == {"Underdog": "available"}
    assert entry["retrieved_at_utc"] == "2026-04-27T12:00:00Z"
    assert entry["fallback_reason"] == "mock_seed"
    assert entry["final_status"] == "available"


def test_deterministic_mock_adapter_supports_new_batch_interface() -> None:
    adapter = DeterministicMockAvailabilityAdapter(
        seed_data={"ars-8:passes": {"alternatives": {"Underdog": "available"}}},
        config=AdapterRuntimeConfig(rate_limit_per_second=5.0, max_retries=4, retry_backoff_seconds=0.1),
    )

    results = adapter.check_batch([Pick(player="ars-8", market="passes", line=52.5)])

    assert len(results) == 1
    assert results[0].available is True
    assert results[0].platform == "mock"
    assert adapter.config.max_retries == 4
