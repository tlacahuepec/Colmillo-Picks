from __future__ import annotations

from datetime import datetime, timezone

from availability.base import AdapterRuntimeConfig, AvailabilityResult, Pick, SportsbookAvailabilityAdapter
from availability.contract import AvailabilityPayload, standardize_availability_payload


class DeterministicMockAvailabilityAdapter(SportsbookAvailabilityAdapter):
    """Deterministic, no-network availability adapter for test and local workflows."""

    def __init__(
        self,
        *,
        seed_data: dict[str, dict[str, object]] | None = None,
        fallback_mode: bool = False,
        fallback_reason: str = "mock_data",
        config: AdapterRuntimeConfig | None = None,
    ) -> None:
        super().__init__(platform="mock", config=config)
        self._seed_data = seed_data or {}
        self._fallback_mode = fallback_mode
        self._fallback_reason = fallback_reason

    def check_availability(self, player: str, market: str, line: float) -> AvailabilityResult:
        key = f"{player}:{market}"
        seed = self._seed_data.get(key, {})
        prizepicks = str(seed.get("prizepicks", "unknown")).lower()
        alternatives = seed.get("alternatives", {})
        alt_available = any(str(status).lower() == "available" for status in alternatives.values()) if isinstance(alternatives, dict) else False
        available = prizepicks == "available" or alt_available
        return AvailabilityResult(
            available=available,
            platform=self.platform,
            odds=seed.get("odds") if isinstance(seed.get("odds"), (float, int)) else None,
            url=str(seed.get("url")) if seed.get("url") else None,
            last_checked=datetime.now(timezone.utc),
        )

    def check_batch(self, picks: list[Pick]) -> list[AvailabilityResult]:
        return super().check_batch(picks)

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
