"""Deterministic NFL heuristics. Scores are rankings, never win probabilities."""

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from nfl_domain import (
    NFL_MARKETS,
    NFL_GAME_MARKETS,
    number,
    resolve_team,
    timestamp,
    valid_offer,
)

_CONFIG = json.loads(
    (Path(__file__).parent.parent / "config.nfl_scoring.json").read_text()
)
_INACTIVE = {"out", "inactive", "suspended", "injured_reserve", "ir", "doubtful"}


def _clip(value):
    return max(0.0, min(1.0, value))


def _exclude(context, subject, reason):
    entry = {"subject": subject, "reason": reason}
    if entry not in context.setdefault("exclusions", []):
        context["exclusions"].append(entry)


def _player_inputs(context, offer, now):
    player = next(
        (
            p
            for p in context.get("players", [])
            if p.get("player_name", "").casefold() == offer["subject_name"].casefold()
        ),
        None,
    )
    if not player or not player.get("source_urls"):
        return None
    game = context["game"]
    if resolve_team(player.get("team", "")) not in {
        game["home_team"],
        game["away_team"],
    }:
        return None
    status = (
        str(player.get("injury_status") or "unknown")
        .strip()
        .casefold()
        .replace(" ", "_")
        .replace("-", "_")
    )
    if status in _INACTIVE:
        return None
    stat = (
        "scorer_touchdowns"
        if offer["market"] == "anytime_touchdown"
        else offer["market"]
    )
    logs = []
    seen_dates = set()
    for log in sorted(
        player.get("game_logs", []), key=lambda g: str(g.get("date", "")), reverse=True
    ):
        date = log.get("date", "")
        try:
            parsed = datetime.strptime(date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if parsed >= now.date() or date in seen_dates or log.get("played") is not True:
            continue
        if log.get("season_type") not in {"regular", "postseason"}:
            continue
        val = number(log.get(stat))
        if val is not None and (
            stat.endswith("_yards") or (val >= 0 and val.is_integer())
        ):
            seen_dates.add(date)
            logs.append(log)
    recent = logs[:5]
    if not recent:
        return None
    flags = []
    if len(recent) < 5:
        flags.append("small_sample")
    if any(log.get("season") != game.get("season") for log in recent):
        flags.append("prior_season_data")
    if status not in {"active", "healthy"}:
        flags.append("availability_uncertain")
    opportunity = number(player.get("opportunity_ratio"))
    matchup = number(player.get("opponent_factor"))
    if opportunity is None or matchup is None:
        flags.append("missing_context")
    production = mean(
        min(1, g[stat]) if stat == "scorer_touchdowns" else g[stat] for g in recent
    )
    return player, production, flags, opportunity, matchup


def _player_factors(context, offer, now):
    inputs = _player_inputs(context, offer, now)
    if inputs is None:
        return None
    player, projected, flags, opportunity, matchup = inputs
    market, selection, line = offer["market"], offer["selection"], offer.get("line")
    if market == "anytime_touchdown":
        edge, scale = projected - 0.5, 0.5
    else:
        edge = (projected - line) * (1 if selection == "over" else -1)
        scale = max(abs(line), 1)
    if edge <= 0:
        return None
    sign = 1 if selection in {"over", "yes"} else -1
    factors = {
        "production": _clip(0.5 + edge / scale),
        "opportunity": _clip(0.5 + sign * ((opportunity or 1) - 1)),
        "matchup": _clip(0.5 + sign * ((matchup or 1) - 1)),
        "availability": 0.5 if "availability_uncertain" in flags else 1.0,
    }
    return factors, flags, projected, player.get("source_urls", [])


def _game_factors(context, offer):
    game = context["game"]
    teams = {resolve_team(t.get("team", "")): t for t in context.get("teams", [])}
    home, away = teams.get(game["home_team"]), teams.get(game["away_team"])
    if not home or not away:
        return None
    fields = (
        "points_for_avg",
        "points_against_avg",
        "points_for_last5",
        "points_against_last5",
    )
    if any(
        not t.get("source_urls")
        or any(number(t.get(f)) is None or t[f] < 0 for f in fields)
        for t in (home, away)
    ):
        return None
    recent_weight = _CONFIG["recent_weight"]

    def blended(team, prefix):
        return (
            recent_weight * team[f"{prefix}_last5"]
            + (1 - recent_weight) * team[f"{prefix}_avg"]
        )

    hp = (blended(home, "points_for") + blended(away, "points_against")) / 2
    ap = (blended(away, "points_for") + blended(home, "points_against")) / 2
    if not game.get("neutral_venue", False):
        hp += _CONFIG["home_advantage_points"]
    flags = []
    for team in (home, away):
        if (number(team.get("games_played")) or 0) < 5:
            flags.append("small_sample")
        if team.get("season") != game.get("season"):
            flags.append("prior_season_data")
        if team.get("qb_status") not in {"active", "healthy"}:
            flags.append("quarterback_uncertain")
    market, selection = offer["market"], offer["selection"]
    weather = context.get("weather") or {}
    wind = number(weather.get("wind_kph"))
    if wind is None and weather.get("roof_closed") is not True:
        flags.append("weather_unknown")
    if market == "total":
        if (
            offer["subject_name"].casefold()
            != f"{game['home_team']} v {game['away_team']}".casefold()
        ):
            return None
        projected = hp + ap
        edge = (projected - offer["line"]) * (1 if selection == "over" else -1)
        scale = max(offer["line"], 1)
        rest = 0.5
    else:
        team = game["home_team"] if selection == "home" else game["away_team"]
        if resolve_team(offer["subject_name"]) != team:
            return None
        projected = (hp - ap) * (1 if selection == "home" else -1)
        edge = projected + (offer["line"] if market == "spread" else 0)
        scale = 14
        hr, ar = number(home.get("rest_days")), number(away.get("rest_days"))
        if hr is None or ar is None:
            flags.append("rest_unknown")
        rest = _clip(
            0.5 + ((hr or 7) - (ar or 7)) * (1 if selection == "home" else -1) / 14
        )
    if edge <= 0:
        return None
    weather_factor = 0.5
    if wind is not None and wind >= 25 and weather.get("roof_closed") is not True:
        flags.append("high_wind")
        if market == "total":
            weather_factor = 0.75 if selection == "under" else 0.25
    factors = {
        "production": _clip(0.5 + edge / scale),
        "rest": rest,
        "availability": 0.25 if "quarterback_uncertain" in flags else 1.0,
        "weather": weather_factor,
    }
    return (
        factors,
        sorted(set(flags)),
        projected,
        home["source_urls"] + away["source_urls"],
    )


def score_nfl(context: dict, *, markets=(), now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    game = context.get("game") or {}
    kickoff = timestamp(game.get("kickoff_utc"))
    if (
        not kickoff
        or kickoff <= now
        or game.get("status") != "scheduled"
        or game.get("season_type") not in {"regular", "postseason"}
        or not game.get("source_urls")
    ):
        _exclude(
            context,
            "game",
            "Game is not verified as an upcoming regular-season or postseason fixture.",
        )
        return []
    requested = set(markets or NFL_MARKETS)
    results = {}
    for offer in context.get("offers", []):
        if not isinstance(offer, dict) or offer.get("market") not in requested:
            continue
        subject = offer.get("subject_name", "Unknown")
        if not valid_offer(offer, now=now):
            _exclude(
                context,
                subject,
                "Offer is incomplete, stale, or outside supported markets.",
            )
            continue
        is_game = offer["market"] in NFL_GAME_MARKETS
        inputs = (
            _game_factors(context, offer)
            if is_game
            else _player_factors(context, offer, now)
        )
        if inputs is None:
            _exclude(
                context,
                subject,
                f"{offer['market']}: insufficient eligible data or no directional support.",
            )
            continue
        factors, flags, projected, sources = inputs
        weights = _CONFIG["game_weights" if is_game else "player_weights"]
        score = sum(factors[k] * weight for k, weight in weights.items())
        if score < _CONFIG["minimum_score"]:
            _exclude(context, subject, f"{offer['market']}: below ranking threshold.")
            continue
        subject_type = (
            "game" if offer["market"] == "total" else "team" if is_game else "player"
        )
        if subject_type == "game":
            subject = f"{game['home_team']} v {game['away_team']}"
        elif subject_type == "team":
            subject = resolve_team(subject)
        pick = {
            "sport": "nfl",
            "player": subject,
            "subject_type": subject_type,
            "subject_name": subject,
            "market": offer["market"],
            "line": offer.get("line"),
            "selection": offer["selection"],
            "direction": offer["selection"],
            "offer": dict(offer),
            "score": round(score, 4),
            "confidence": "medium"
            if not flags and score >= _CONFIG["medium_confidence"]
            else "low",
            "projection": round(projected, 3),
            "availability_status": "unknown",
            "explainability": {
                "risk_flags": flags,
                "top_contributing_factors": [
                    {"factor": k, "score": round(v, 4), "weight": weights[k]}
                    for k, v in factors.items()
                ],
                "sources": sorted(set(sources)),
                "rationale": "Recent production supports the offered selection. Score is a heuristic ranking, not a win probability or expected return.",
            },
        }
        key = (subject, offer["market"], offer.get("line"), offer["selection"])
        old = results.get(key)
        if old is None or (offer["odds_decimal"], offer["sportsbook"]) > (
            old["offer"]["odds_decimal"],
            old["offer"]["sportsbook"],
        ):
            results[key] = pick
    if not results:
        _exclude(
            context,
            "game",
            "No verified offers with sufficient supporting data qualified.",
        )
    return sorted(
        results.values(),
        key=lambda p: (-p["score"], p["subject_name"], p["market"], str(p["line"])),
    )
