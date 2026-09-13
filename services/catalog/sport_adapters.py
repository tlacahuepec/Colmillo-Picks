"""Provider-backed adapters for normalized daily catalog snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from services.catalog.contracts import (
    CatalogEvent,
    CatalogField,
    CatalogSnapshot,
    CompletenessStatus,
    Confidence,
    FreshnessStatus,
    InjurySnapshot,
    LineupSnapshot,
    SourceObservation,
)
from services.catalog.providers import (
    CatalogProvider,
    ProviderRequest,
    ProviderResult,
    ProviderStatus,
    canonical_ref,
    normalize_event,
)


@dataclass(frozen=True)
class SportCatalogConfig:
    """Sport-specific resource names and fields required for a usable snapshot."""

    sport: str
    league: str
    required_fields: tuple[str, ...]
    resources: tuple[str, ...] = ("lineups", "injuries", "form", "weather", "markets")


SOCCER_CATALOG_CONFIG = SportCatalogConfig(
    sport="soccer",
    league="soccer",
    required_fields=("lineups", "injuries", "markets"),
)

BASKETBALL_CATALOG_CONFIG = SportCatalogConfig(
    sport="basketball",
    league="basketball",
    required_fields=("lineups", "injuries", "markets"),
)

MLB_CATALOG_CONFIG = SportCatalogConfig(
    sport="baseball",
    league="mlb",
    required_fields=("lineups", "injuries", "markets"),
)

NFL_CATALOG_CONFIG = SportCatalogConfig(
    sport="nfl",
    league="nfl",
    required_fields=("lineups", "injuries", "markets"),
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SoccerCatalogAdapter:
    """Normalize soccer provider responses without exposing provider payloads."""

    def __init__(
        self,
        *,
        schedule_provider: CatalogProvider,
        providers: Mapping[str, CatalogProvider],
        clock: Callable[[], str] = _now_utc,
        config: SportCatalogConfig = SOCCER_CATALOG_CONFIG,
    ) -> None:
        self._schedule_provider = schedule_provider
        self._providers = dict(providers)
        self._clock = clock
        self._config = config

    def discover(self, run_date: str) -> list[CatalogEvent]:
        result = self._schedule_provider.fetch(ProviderRequest(
            sport=self._config.sport, resource="schedule", requested_at=self._clock(), date=run_date,
        ))
        if result.status == ProviderStatus.UNAVAILABLE:
            return []
        events: list[CatalogEvent] = []
        for raw in result.facts.get("matches", []):
            if not isinstance(raw, Mapping):
                continue
            event, _ = normalize_event(
                raw=raw, sport=self._config.sport, league=str(raw.get("league") or self._config.league),
                provider=result.provider, observed_at=result.retrieved_at,
            )
            events.append(event)
        return events

    def collect(self, event: CatalogEvent) -> dict[str, ProviderResult]:
        collected: dict[str, ProviderResult] = {}
        for resource in self._config.resources:
            provider = self._providers.get(resource)
            if provider is None:
                continue
            collected[resource] = provider.fetch(ProviderRequest(
                sport=self._config.sport, resource=resource, requested_at=self._clock(), event_id=event.event_id,
            ))
        return collected

    def normalize(self, event: CatalogEvent, raw: Mapping[str, ProviderResult]) -> CatalogSnapshot:
        created_at = self._clock()
        fields: list[CatalogField] = []
        lineups: list[LineupSnapshot] = []
        injuries: list[InjurySnapshot] = []
        observations: list[SourceObservation] = []
        missing: list[str] = []
        for resource in self._config.resources:
            result = raw.get(resource)
            if result is None or result.status == ProviderStatus.UNAVAILABLE:
                missing.append(resource)
                continue
            if result.observation:
                observations.append(result.observation)
            facts = result.facts
            if resource == "lineups":
                lineups.extend(_lineups(event, facts, result))
            elif resource == "injuries":
                injuries.extend(_injuries(event, facts, result))
            else:
                for name, value in facts.items():
                    if isinstance(name, str) and value is not None:
                        fields.append(CatalogField(
                            name=name, value=value, observed_at=result.retrieved_at,
                            freshness=FreshnessStatus.FRESH, confidence=Confidence.CONFIRMED,
                            observation_id=result.observation.observation_id if result.observation else None,
                        ))
            if result.status == ProviderStatus.PARTIAL:
                missing.append(resource)
        if not lineups and "lineups" not in missing:
            missing.append("lineups")
        if not injuries and "injuries" not in missing:
            missing.append("injuries")
        completeness = CompletenessStatus.COMPLETE if not missing else CompletenessStatus.PARTIAL
        return CatalogSnapshot(
            snapshot_id=f"{event.event_id}:{created_at}", event=event, created_at=created_at,
            as_of=created_at, completeness=completeness, fields=tuple(fields),
            lineups=tuple(lineups), injuries=tuple(injuries),
            source_observations=tuple(observations), missing_fields=tuple(sorted(set(missing))),
        )

    @staticmethod
    def validate(snapshot: CatalogSnapshot) -> list[str]:
        return list(snapshot.missing_fields)


class BasketballCatalogAdapter(SoccerCatalogAdapter):
    """Basketball adapter using the shared normalized resource pipeline."""

    def __init__(self, *, schedule_provider: CatalogProvider,
                 providers: Mapping[str, CatalogProvider],
                 clock: Callable[[], str] = _now_utc) -> None:
        super().__init__(schedule_provider=schedule_provider, providers=providers,
                         clock=clock, config=BASKETBALL_CATALOG_CONFIG)


class MlbCatalogAdapter(SoccerCatalogAdapter):
    """MLB adapter using the shared normalized resource pipeline."""

    def __init__(self, *, schedule_provider: CatalogProvider,
                 providers: Mapping[str, CatalogProvider],
                 clock: Callable[[], str] = _now_utc) -> None:
        super().__init__(schedule_provider=schedule_provider, providers=providers,
                         clock=clock, config=MLB_CATALOG_CONFIG)


class NflCatalogAdapter(SoccerCatalogAdapter):
    """NFL adapter using the shared normalized resource pipeline."""

    def __init__(self, *, schedule_provider: CatalogProvider,
                 providers: Mapping[str, CatalogProvider],
                 clock: Callable[[], str] = _now_utc) -> None:
        super().__init__(schedule_provider=schedule_provider, providers=providers,
                         clock=clock, config=NFL_CATALOG_CONFIG)


def _lineups(event: CatalogEvent, facts: Mapping[str, Any], result: ProviderResult) -> list[LineupSnapshot]:
    output: list[LineupSnapshot] = []
    for item in facts.get("lineups", []):
        if not isinstance(item, Mapping):
            continue
        team_id = str(item.get("team_id") or item.get("team") or "unknown")
        players = tuple(canonical_ref(event.sport, "player", provider_id=str(player.get("id")) if isinstance(player, Mapping) and player.get("id") else None, display_name=str(player.get("name") if isinstance(player, Mapping) else player)) for player in item.get("players", []))
        output.append(LineupSnapshot(
            event_id=event.event_id, team_id=team_id,
            status=Confidence(str(item.get("status") or "projected")), players=players,
            formation=str(item["formation"]) if item.get("formation") else None,
            observed_at=result.retrieved_at,
            observation_id=result.observation.observation_id if result.observation else None,
        ))
    return output


def _injuries(event: CatalogEvent, facts: Mapping[str, Any], result: ProviderResult) -> list[InjurySnapshot]:
    output: list[InjurySnapshot] = []
    for item in facts.get("injuries", []):
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("player") or item.get("name") or "unknown")
        output.append(InjurySnapshot(
            event_id=event.event_id,
            subject=canonical_ref(event.sport, "player", provider_id=str(item.get("player_id")) if item.get("player_id") else None, display_name=name),
            status=str(item.get("status") or "unknown"), reason=str(item["reason"]) if item.get("reason") else None,
            expected_return=str(item["expected_return"]) if item.get("expected_return") else None,
            observed_at=result.retrieved_at,
            observation_id=result.observation.observation_id if result.observation else None,
        ))
    return output
