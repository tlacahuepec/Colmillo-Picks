"""MLB prop lines adapter connecting catalog odds providers to MLBCollectionService."""

from __future__ import annotations

from datetime import datetime, timezone

from baseball_domain import MLBPropLine
from mlb_provider_ports import MLBPropLinesResult, MLBProviderMeta
from services.catalog.providers import CatalogProvider, ProviderRequest, ProviderStatus


class MLBPropLinesAdapter:
    """Implements MLBPropLinesPort backed by a CatalogProvider (default TheOddsApiAdapter)."""

    def __init__(self, *, provider: CatalogProvider | None = None) -> None:
        if provider is None:
            from services.catalog.odds_provider import TheOddsApiAdapter

            self._provider: CatalogProvider = TheOddsApiAdapter()
        else:
            self._provider = provider

    def get_prop_lines(
        self,
        *,
        game_pk: int,
        home_team: str,
        away_team: str,
        date: str,
        players: list[str] | None = None,
    ) -> MLBPropLinesResult:
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        params: dict[str, str] = {
            "home_team": home_team,
            "away_team": away_team,
            "date": date,
            "game_pk": str(game_pk),
        }
        if players:
            params["players"] = ", ".join(players)

        request = ProviderRequest(
            sport="baseball",
            resource="odds",
            requested_at=now_utc,
            date=date,
            parameters=params,
        )
        try:
            result = self._provider.fetch(request)
            if result.status == ProviderStatus.AVAILABLE:
                raw_props = result.facts.get("player_props", [])
                converted: list[MLBPropLine] = []
                for prop in raw_props:
                    if not isinstance(prop, dict):
                        continue
                    p_name = prop.get("player_name")
                    m_key = prop.get("market")
                    line_val = prop.get("line")
                    if p_name and m_key and line_val is not None:
                        converted.append(
                            MLBPropLine(
                                player_name=str(p_name),
                                market=str(m_key),
                                line=float(line_val),
                                over_odds=prop.get("over_odds"),
                                under_odds=prop.get("under_odds"),
                                source=str(prop.get("source", result.provider)),
                                retrieved_at_utc=result.retrieved_at,
                            )
                        )
                return MLBPropLinesResult(
                    meta=MLBProviderMeta(
                        available=True,
                        source=result.provider,
                        retrieved_at_utc=result.retrieved_at,
                        provider_status=result.status.value,
                    ),
                    prop_lines=converted,
                )
            else:
                return MLBPropLinesResult(
                    meta=MLBProviderMeta(
                        available=False,
                        source=result.provider,
                        retrieved_at_utc=result.retrieved_at,
                        provider_status=result.status.value,
                        error_message=str(result.error_category) if result.error_category else None,
                    ),
                    prop_lines=[],
                )
        except Exception as exc:
            return MLBPropLinesResult(
                meta=MLBProviderMeta(
                    available=False,
                    source=getattr(self._provider, "provider_name", "unknown"),
                    retrieved_at_utc=now_utc,
                    provider_status="unavailable",
                    error_message=str(exc),
                ),
                prop_lines=[],
            )
