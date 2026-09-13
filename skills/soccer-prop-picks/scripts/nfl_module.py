"""NFL integration with the shared sport pipeline."""

from diagnostics_support import emit, error_info

from nfl_domain import NFL_MARKETS, resolve_team
from nfl_scoring import score_nfl

class NflDataQualityError(RuntimeError):
    """NFL provider collection failed, as opposed to verified absence of picks."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__("NFL collection failed.")


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
            if not data.get("offers") and data.get("provider_errors"):
                raise NflDataQualityError({
                    "error_code": "nfl_provider_failure",
                    "provider_errors": data["provider_errors"],
                }) from getattr(collector, "last_provider_error", None)
        except Exception as exc:
            reason = error_info(exc)
            emit("nfl_collection_failed", stage="collect", level="ERROR",
                 outcome="failed", sport="nfl", **reason)
            if isinstance(exc, NflDataQualityError):
                raise
            raise NflDataQualityError(reason) from exc
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
        scores = score_nfl(match_inputs, markets=markets)
        if not scores and match_inputs.get("provider_errors"):
            raise NflDataQualityError({
                "error_code": "nfl_provider_failure",
                "provider_errors": match_inputs["provider_errors"],
            })
        return scores

    def explain(self, scored_pick):
        return scored_pick.get("explainability", {}).get(
            "rationale", "No supported recommendation."
        )
