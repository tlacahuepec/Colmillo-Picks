"""Basketball prop lines adapter connecting catalog odds providers to BasketballModule."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.catalog.providers import CatalogProvider, ProviderRequest, ProviderStatus


class BasketballPropLinesAdapter:
    """Provides NBA player prop lines backed by a CatalogProvider (default TheOddsApiAdapter)."""

    def __init__(self, *, provider: CatalogProvider | None = None) -> None:
        if provider is None:
            from services.catalog.odds_provider import TheOddsApiAdapter

            self._provider: CatalogProvider = TheOddsApiAdapter()
        else:
            self._provider = provider

    def get_prop_lines(
        self,
        *,
        players: list[dict[str, Any]],
        markets: tuple[str, ...],
    ) -> dict[str, dict[str, Any]] | None:
        if not players:
            return {}

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        player_names = [p.get("player_name", "") for p in players if p.get("player_name")]
        teams = list({p.get("team") for p in players if p.get("team")})

        home_team = teams[0] if len(teams) > 0 else ""
        away_team = teams[1] if len(teams) > 1 else ""

        request = ProviderRequest(
            sport="basketball",
            resource="odds",
            requested_at=now_utc,
            parameters={
                "home_team": home_team,
                "away_team": away_team,
                "players": ", ".join(player_names),
                "markets": ", ".join(markets),
            },
        )

        try:
            result = self._provider.fetch(request)
            if result.status != ProviderStatus.AVAILABLE:
                return None

            raw_props = result.facts.get("player_props", [])
            lines_by_player: dict[str, dict[str, Any]] = {}

            # Map from lower-case name to original name in players list
            name_lookup = {p_name.lower(): p_name for p_name in player_names}

            for prop in raw_props:
                if not isinstance(prop, dict):
                    continue
                p_name = str(prop.get("player_name", ""))
                market = str(prop.get("market", ""))
                line_val = prop.get("line")

                if not p_name or not market or line_val is None:
                    continue

                if markets and market not in markets:
                    continue

                # Match player name
                matched_name = name_lookup.get(p_name.lower())
                if not matched_name:
                    # Check substring match
                    for target_lower, target_orig in name_lookup.items():
                        if target_lower in p_name.lower() or p_name.lower() in target_lower:
                            matched_name = target_orig
                            break

                target_key = matched_name or p_name
                try:
                    num_line = float(line_val)
                    lines_by_player.setdefault(target_key, {})[market] = {
                        "line": num_line,
                        "market_agreement": 1.0,
                        "sources": [
                            {
                                "source": str(prop.get("bookmaker", result.provider)),
                                "line": num_line,
                            }
                        ],
                    }
                except (ValueError, TypeError):
                    continue

            return lines_by_player

        except Exception:
            return None
