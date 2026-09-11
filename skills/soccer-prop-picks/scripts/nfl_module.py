"""NFL integration with the shared sport pipeline."""

import logging

from nfl_domain import NFL_MARKETS, resolve_team
from nfl_scoring import score_nfl

logger = logging.getLogger(__name__)


class NflNoPicks(RuntimeError):
    """A verified NFL analysis did not produce any eligible recommendations."""


class NflModule:
    sport_id = "nfl"
    supported_leagues = {"nfl"}
    supported_markets = set(NFL_MARKETS)

    def __init__(
        self, *, collector=None, provider=None, model=None, timezone_name=None
    ):
        self.collector = collector
        self.provider = provider
        self.model = model
        self.timezone_name = timezone_name

    def collect_inputs(self, *, home_team, away_team, match_date, league=None):
        try:
            collector = self.collector
            if collector is None:
                from nfl_collection import NflCollector

                collector = NflCollector.from_env(
                    provider=self.provider,
                    model=self.model,
                    timezone_name=self.timezone_name,
                )
            data = collector(
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                league=league,
            )
        except Exception as exc:
            logger.warning("NFL collection unavailable (%s)", type(exc).__name__)
            data = {
                "game": None,
                "players": [],
                "offers": [],
                "provider_statuses": {"context": "unavailable"},
                "exclusions": [
                    {
                        "subject": "game",
                        "reason": "NFL collection unavailable or invalid. Check provider configuration and search support.",
                    }
                ],
            }
        game = data.get("game") or {}
        data.update(
            home_team=game.get("home_team") or resolve_team(home_team),
            away_team=game.get("away_team") or resolve_team(away_team),
            match_date=match_date,
            league="nfl",
            sport="nfl",
        )
        return data

    def score(self, match_inputs, *, markets=()):
        return score_nfl(match_inputs, markets=markets)

    def explain(self, scored_pick):
        return scored_pick.get("explainability", {}).get(
            "rationale", "No supported recommendation."
        )
