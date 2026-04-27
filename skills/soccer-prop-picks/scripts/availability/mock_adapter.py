from __future__ import annotations

from availability.contract import AvailabilityAdapter, AvailabilityPayload, standardize_availability_payload


class DeterministicMockAvailabilityAdapter(AvailabilityAdapter):
    """Deterministic, no-network availability adapter for test and local workflows."""

    def __init__(
        self,
        *,
        seed_data: dict[str, dict[str, object]] | None = None,
        fallback_mode: bool = False,
        fallback_reason: str = "mock_data",
    ) -> None:
        self._seed_data = seed_data or {}
        self._fallback_mode = fallback_mode
        self._fallback_reason = fallback_reason

    def check_picks(self, picks: list[dict[str, str]]) -> AvailabilityPayload:
        keys = [f"{pick.get('player_id', 'unknown')}:{pick.get('market', 'unknown')}" for pick in picks]
        return standardize_availability_payload(
            {
                "fallback_mode": self._fallback_mode,
                "fallback_reason": self._fallback_reason,
                "picks": self._seed_data,
            },
            pick_keys=keys,
        )
