"""NFL integration with the shared sport pipeline."""

from diagnostics_support import emit, error_info

from nfl_domain import NFL_MARKETS, resolve_team
from nfl_scoring import score_nfl

class NflDataQualityError(RuntimeError):
    """NFL provider collection failed, as opposed to verified absence of picks."""

    def __init__(self, reason):
        self.reason = reason
        summary = reason.get("recommendation_summary", {}) if isinstance(reason, dict) else {}
        super().__init__(summary.get("message") or "NFL collection failed.")


class NflNoPicks(RuntimeError):
    """A verified NFL analysis did not produce any eligible recommendations."""


def nfl_recommendation_summary(data, scores=()):
    """Return a bounded, customer-safe explanation of the NFL terminal result."""
    offers = data.get("offers") or []
    exclusions = data.get("exclusions") or []
    rejections = data.get("offer_rejections") or []
    counts = {"verified_offers": len(offers), "excluded_inputs": len(exclusions),
              "rejected_offers": len(rejections), "provider_failures": len(data.get("provider_errors") or {})}
    if scores:
        return {"code": "recommendations_available", "message": "Verified NFL recommendations are available.", "counts": counts}
    if not data.get("game"):
        return {"code": "fixture_unverified", "message": "This fixture could not be verified. Check the teams and local game date, then try again.", "counts": counts}
    if data.get("provider_errors"):
        return {"code": "provider_failure", "message": "Sportsbook data could not be collected. No odds were substituted; try again shortly.", "counts": counts}
    if not offers:
        return {"code": "offers_unavailable", "message": "The fixture was verified, but no supported sportsbook offers were available.", "counts": counts}
    if exclusions:
        return {"code": "insufficient_supported_data", "message": "Offers were found, but the supporting NFL data was insufficient for a verified recommendation.", "counts": counts}
    return {"code": "no_qualifying_selection", "message": "Analysis completed: verified offers were evaluated, but none met the ranking threshold.", "counts": counts}


class NflModule:
    sport_id = "nfl"
    supported_leagues = {"nfl"}
    supported_markets: set[str] = set(NFL_MARKETS)

    def __init__(
        self, *, collector=None, provider=None, model=None, timezone_name=None
    ):
        self.collector = collector
        self.provider = provider
        self.model = model
        self.timezone_name = timezone_name

    def collect_inputs(self, *, home_team, away_team, match_date, league=None, markets=()):
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
                markets=markets,
            )
            if not data.get("offers") and data.get("provider_errors"):
                summary = nfl_recommendation_summary(data)
                raise NflDataQualityError({
                    "error_code": "nfl_provider_failure",
                    "provider_errors": data["provider_errors"],
                    "recommendation_summary": summary,
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
        data["recommendation_summary"] = nfl_recommendation_summary(data)
        return data

    def score(self, match_inputs, *, markets=()):
        scores = score_nfl(match_inputs, markets=markets)
        match_inputs["recommendation_summary"] = nfl_recommendation_summary(match_inputs, scores)
        if not scores and match_inputs.get("provider_errors"):
            raise NflDataQualityError({
                "error_code": "nfl_provider_failure",
                "provider_errors": match_inputs["provider_errors"],
                "recommendation_summary": match_inputs["recommendation_summary"],
            })
        return scores

    def explain(self, scored_pick):
        return scored_pick.get("explainability", {}).get(
            "rationale", "No supported recommendation."
        )
