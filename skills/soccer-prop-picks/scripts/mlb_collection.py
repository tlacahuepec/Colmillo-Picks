"""MLB collection service — orchestrates provider calls into MLBGameContext."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from baseball_domain import (
    BaseballProviderStatus,
    BallparkInfo,
    MLBBattingOrder,
    MLBBattingOrderSlot,
    MLBBullpenArm,
    MLBBullpenState,
    MLBGame,
    MLBGameContext,
    MLBProbablePitcher,
    MLBWeather,
)
from mlb_provider_ports import (
    BallparkPort,
    BallparkResult,
    BullpenPort,
    BullpenResult,
    MLBLineupsPort,
    MLBLineupsResult,
    MLBPlayerStatsPort,
    MLBProviderMeta,
    MLBSchedulePort,
    MLBWeatherPort,
    MLBWeatherResult,
    PlayerSplitsPort,
    ProbablePitcherPort,
    ProbablePitcherResult,
)

logger = logging.getLogger("colmillo.mlb_collection")


@dataclass
class MLBCollectionConfig:
    freshness_threshold_minutes: int = 30
    require_pitcher_for_prediction: bool = True
    require_lineup_for_prediction: bool = True


class MLBCollectionService:
    def __init__(
        self,
        *,
        schedule: MLBSchedulePort,
        pitchers: ProbablePitcherPort,
        lineups: MLBLineupsPort,
        player_stats: MLBPlayerStatsPort,
        splits: PlayerSplitsPort,
        bullpen: BullpenPort,
        weather: MLBWeatherPort,
        ballpark: BallparkPort,
        config: MLBCollectionConfig | None = None,
    ) -> None:
        self._schedule = schedule
        self._pitchers = pitchers
        self._lineups = lineups
        self._player_stats = player_stats
        self._splits = splits
        self._bullpen = bullpen
        self._weather = weather
        self._ballpark = ballpark
        self._config = config or MLBCollectionConfig()

    def collect(
        self,
        *,
        game_pk: int,
        game: MLBGame,
        player_ids: list[int] | None = None,
        season: int | None = None,
    ) -> MLBGameContext:
        pitcher_result = self._safe_call_pitchers(game_pk)
        lineup_result = self._safe_call_lineups(game_pk)
        bullpen_home = self._safe_call_bullpen(game.home_team_id, game.game_time_utc[:10] if game.game_time_utc else "")
        bullpen_away = self._safe_call_bullpen(game.away_team_id, game.game_time_utc[:10] if game.game_time_utc else "")
        weather_result = self._safe_call_weather(game_pk, game.game_time_utc)
        ballpark_result = self._safe_call_ballpark(game.venue_id)

        home_pitcher = _build_probable_pitcher(pitcher_result, "home")
        away_pitcher = _build_probable_pitcher(pitcher_result, "away")
        home_order = _build_batting_order(lineup_result, "home")
        away_order = _build_batting_order(lineup_result, "away")
        home_bullpen = _build_bullpen_state(bullpen_home, game.home_team)
        away_bullpen = _build_bullpen_state(bullpen_away, game.away_team)
        weather_model = _build_weather(weather_result)
        ballpark_model = _build_ballpark(ballpark_result)

        provider_status = self._aggregate_status(
            pitcher_result, lineup_result, weather_result, bullpen_home
        )

        ctx = MLBGameContext(
            game=game,
            home_probable_pitcher=home_pitcher,
            away_probable_pitcher=away_pitcher,
            home_batting_order=home_order,
            away_batting_order=away_order,
            home_bullpen=home_bullpen,
            away_bullpen=away_bullpen,
            weather=weather_model,
            ballpark=ballpark_model,
            provider_status=provider_status,
            retrieved_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

        should_reject, reasons = _should_reject(ctx, self._config)
        ctx.should_reject_prediction = should_reject
        ctx.rejection_reasons = reasons

        return ctx

    def _safe_call_pitchers(self, game_pk: int) -> ProbablePitcherResult | None:
        try:
            result = self._pitchers.get_probable_pitchers(game_pk=game_pk)
            if not result.meta.available:
                logger.warning(
                    "mlb_pitchers_unavailable",
                    extra={"game_pk": game_pk, "error_message": result.meta.error_message},
                )
            return result
        except Exception as exc:
            logger.warning("mlb_pitchers_call_failed", extra={"game_pk": game_pk, "error": str(exc)})
            return None

    def _safe_call_lineups(self, game_pk: int) -> MLBLineupsResult | None:
        try:
            result = self._lineups.get_lineups(game_pk=game_pk)
            if not result.meta.available:
                logger.warning(
                    "mlb_lineups_unavailable",
                    extra={"game_pk": game_pk, "error_message": result.meta.error_message},
                )
            return result
        except Exception as exc:
            logger.warning("mlb_lineups_call_failed", extra={"game_pk": game_pk, "error": str(exc)})
            return None

    def _safe_call_bullpen(self, team_id: int | None, date: str) -> BullpenResult | None:
        if team_id is None:
            return None
        try:
            return self._bullpen.get_bullpen_state(team_id=team_id, date=date)
        except Exception as exc:
            logger.warning("mlb_bullpen_call_failed", extra={"team_id": team_id, "error": str(exc)})
            return None

    def _safe_call_weather(self, game_pk: int, game_time_utc: str) -> MLBWeatherResult | None:
        try:
            return self._weather.get_weather(game_pk=game_pk, game_time_utc=game_time_utc)
        except Exception as exc:
            logger.warning("mlb_weather_call_failed", extra={"game_pk": game_pk, "error": str(exc)})
            return None

    def _safe_call_ballpark(self, venue_id: int | None) -> BallparkResult | None:
        if venue_id is None:
            return None
        try:
            return self._ballpark.get_ballpark(venue_id=venue_id)
        except Exception as exc:
            logger.warning("mlb_ballpark_call_failed", extra={"venue_id": venue_id, "error": str(exc)})
            return None

    def _aggregate_status(
        self,
        pitcher_result: ProbablePitcherResult | None,
        lineup_result: MLBLineupsResult | None,
        weather_result: MLBWeatherResult | None,
        bullpen_result: BullpenResult | None,
    ) -> BaseballProviderStatus:
        return BaseballProviderStatus(
            stats="ok",
            lineup=_meta_to_status(lineup_result.meta if lineup_result else None, self._config.freshness_threshold_minutes),
            weather=_meta_to_status(weather_result.meta if weather_result else None, self._config.freshness_threshold_minutes),
            bullpen=_meta_to_status(bullpen_result.meta if bullpen_result else None, self._config.freshness_threshold_minutes),
            odds="ok",
        )


def _meta_to_status(meta: MLBProviderMeta | None, threshold_minutes: int) -> str:
    if meta is None:
        return "unavailable"
    if not meta.available:
        return "unavailable"
    return _check_freshness(meta, threshold_minutes)


def _check_freshness(meta: MLBProviderMeta, threshold_minutes: int) -> str:
    if not meta.available:
        return "unavailable"
    if meta.retrieved_at_utc is None:
        return "ok"
    try:
        retrieved = datetime.fromisoformat(meta.retrieved_at_utc.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - retrieved
        if age > timedelta(minutes=threshold_minutes):
            return "stale"
    except (ValueError, TypeError):
        pass
    return "ok"


def _build_probable_pitcher(
    result: ProbablePitcherResult | None, side: str
) -> MLBProbablePitcher | None:
    if result is None or not result.meta.available:
        return None
    pitcher_data = result.home_pitcher if side == "home" else result.away_pitcher
    if pitcher_data is None:
        return None
    return MLBProbablePitcher(
        player_name=pitcher_data.get("fullName", "Unknown"),
        player_id=pitcher_data.get("id"),
        confirmed=pitcher_data.get("confirmed", False),
    )


def _build_batting_order(
    result: MLBLineupsResult | None, side: str
) -> MLBBattingOrder | None:
    if result is None or not result.meta.available:
        return None
    order_data = result.home_order if side == "home" else result.away_order
    if not order_data:
        return MLBBattingOrder(team=side, confirmed=result.confirmed, slots=[])
    slots = [
        MLBBattingOrderSlot(
            position=idx + 1,
            player_name=p.get("fullName", "Unknown"),
            player_id=p.get("id"),
            field_position=p.get("position"),
        )
        for idx, p in enumerate(order_data)
    ]
    return MLBBattingOrder(team=side, confirmed=result.confirmed, slots=slots)


def _build_bullpen_state(
    result: BullpenResult | None, team: str
) -> MLBBullpenState | None:
    if result is None or not result.meta.available:
        return None
    arms = [
        MLBBullpenArm(
            player_name=arm.get("fullName", "Unknown"),
            player_id=arm.get("id"),
            available=arm.get("available", True),
        )
        for arm in result.arms
    ]
    return MLBBullpenState(team=team, arms=arms)


def _build_weather(result: MLBWeatherResult | None) -> MLBWeather | None:
    if result is None or not result.meta.available:
        return None
    return MLBWeather(
        temp_f=result.temp_f,
        wind_mph=result.wind_mph,
        wind_direction=result.wind_direction,
        dome=result.dome,
        source=result.meta.source,
        retrieved_at_utc=result.meta.retrieved_at_utc,
    )


def _build_ballpark(result: BallparkResult | None) -> BallparkInfo | None:
    if result is None or not result.meta.available:
        return None
    return BallparkInfo(
        name=result.venue_name,
        park_factor=result.park_factor,
        hr_factor=result.hr_factor,
    )


def _should_reject(
    ctx: MLBGameContext, config: MLBCollectionConfig
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    pitcher_confirmed = False
    if ctx.home_probable_pitcher and ctx.home_probable_pitcher.confirmed:
        pitcher_confirmed = True
    if ctx.away_probable_pitcher and ctx.away_probable_pitcher.confirmed:
        pitcher_confirmed = True

    lineup_confirmed = False
    if ctx.home_batting_order and ctx.home_batting_order.confirmed:
        lineup_confirmed = True
    if ctx.away_batting_order and ctx.away_batting_order.confirmed:
        lineup_confirmed = True

    if not pitcher_confirmed and config.require_pitcher_for_prediction:
        reasons.append("no_confirmed_pitcher")
    if not lineup_confirmed and config.require_lineup_for_prediction:
        reasons.append("no_confirmed_lineup")

    should_reject = (
        not pitcher_confirmed
        and not lineup_confirmed
        and config.require_pitcher_for_prediction
        and config.require_lineup_for_prediction
    )

    return should_reject, reasons
