from __future__ import annotations

import json


def build_daily_intelligence_system_prompt() -> str:
    return (
        "You are a real-time soccer intelligence analyst. "
        "You have access to live news, injury updates, confirmed and projected lineups, and current betting odds. "
        "Use your web search capabilities to retrieve the most current information available as of today. "
        "Return exactly one valid JSON object. Do not include markdown, code fences, or any prose outside the JSON. "
        "If current data is unavailable for a field, use null rather than guessing or fabricating. "
        "Never invent player injuries, lineup data, or odds that are not verifiable."
    )


def build_daily_intelligence_user_prompt(*, date_utc: str, top_n: int) -> str:
    payload = {
        "task": f"Identify the top {top_n} most important soccer matches on {date_utc}",
        "today_utc": date_utc,
        "selection_criteria": [
            (
                "Prioritize: Champions League, Europa League, Premier League, La Liga, "
                "Serie A, Bundesliga, Ligue 1, Copa America, World Cup qualifiers"
            ),
            (
                "Weight by stakes: title race, relegation battle, knockout elimination, "
                "city/regional derby, top-4 race"
            ),
            "Include only matches scheduled within 24 hours of today_utc",
        ],
        "per_match_data_required": [
            "injuries and suspensions for key players (starters, top scorers, key playmakers)",
            "projected or confirmed starting lineup with formation",
            "current 1X2 match odds from any available sportsbook or consensus source",
        ],
        "required_json_shape": {
            "schema_version": "v1.0.0",
            "date_utc": "YYYY-MM-DD",
            "generated_at_utc": "ISO-8601Z timestamp",
            "provider": "xai",
            "model": "model name used",
            "top_matches": [
                {
                    "rank": 1,
                    "match_importance": "high|medium|low",
                    "competition": "competition name",
                    "kickoff_utc": "ISO-8601Z or null",
                    "venue": {"name": "str", "city": "str", "country": "str"},
                    "teams": {
                        "home": {"name": "str", "team_id": "stable code or null"},
                        "away": {"name": "str", "team_id": "stable code or null"},
                    },
                    "injuries": [
                        {
                            "team": "team name",
                            "player": "player name",
                            "status": "out|doubtful|questionable|suspended",
                            "reason": "str or null",
                        }
                    ],
                    "projected_lineups": {
                        "home": {
                            "formation": "e.g. 4-3-3 or null",
                            "starters": ["player full name"],
                            "status": "confirmed|projected|unknown",
                        },
                        "away": {
                            "formation": "e.g. 4-2-3-1 or null",
                            "starters": ["player full name"],
                            "status": "confirmed|projected|unknown",
                        },
                    },
                    "odds": {
                        "home_win": 1.85,
                        "draw": 3.50,
                        "away_win": 4.20,
                        "source": "sportsbook name or null",
                        "captured_at_utc": "ISO-8601Z or null",
                    },
                    "notes": "any high-signal intelligence for this match or null",
                }
            ],
        },
        "rules": [
            "Return only JSON — no markdown fences, no prose outside the JSON",
            "Use null for any field where current data is unavailable or unverifiable",
            "Do not fabricate injuries, lineup starters, or odds",
            f"Include at most {top_n} matches, ranked 1 (most important) to {top_n}",
            "Populate generated_at_utc with the actual UTC time of your response",
            "Populate model with the model identifier you are running on",
        ],
    }
    return json.dumps(payload, sort_keys=True)


def build_match_discovery_system_prompt() -> str:
    return (
        "You are a real-time multi-sport match discovery analyst. "
        "Use current, verifiable sources to identify important scheduled matches. "
        "Return exactly one valid JSON object. Do not include markdown, code fences, or prose outside the JSON. "
        "Use null for unavailable or unverifiable fields, and include error metadata per sport when a sport cannot be discovered. "
        "Never invent fixtures, kickoff times, leagues, or sources."
    )


def build_match_discovery_user_prompt(
    *,
    date_utc: str,
    sports: list[str],
    limit_per_sport: int,
) -> str:
    payload = {
        "task": (
            f"Identify up to {limit_per_sport} important matches per requested sport on {date_utc}."
        ),
        "today_utc": date_utc,
        "sports": sports,
        "limit_per_sport": limit_per_sport,
        "selection_criteria_by_sport": {
            "soccer": [
                "Major competitions, derbies, title races, relegation battles, knockout matches, and top-four races",
                "Prefer matches with clear kickoff time and competition context",
            ],
            "basketball": [
                "NBA, EuroLeague, or NCAAB games with playoff, rivalry, rest, injury, or standings significance",
                "Prefer games with clear home and away teams and scheduled tip time",
            ],
            "baseball": [
                "MLB games with notable pitchers, rivalry context, playoff relevance, or strong market interest",
                "Prefer games with clear probable teams and scheduled first pitch",
            ],
        },
        "required_json_shape": {
            "schema_version": "v1.0.0",
            "date_utc": "YYYY-MM-DD",
            "generated_at_utc": "ISO-8601Z timestamp",
            "provider": "provider name",
            "model": "model name used",
            "grouped_by_sport": {
                "soccer": {
                    "matches": [
                        {
                            "home_team": "str",
                            "away_team": "str",
                            "event_date": "YYYY-MM-DD",
                            "league": "stable league key or null",
                            "competition": "display competition name or null",
                            "kickoff_utc": "ISO-8601Z or null",
                            "importance": "high|medium|low",
                            "notes": "short rationale or null",
                            "sources": [
                                {"label": "source label", "url": "https://... or null"}
                            ],
                            "data_quality": {
                                "confidence": "high|medium|low",
                                "missing_fields": ["field name"],
                            },
                        }
                    ],
                    "error": None,
                    "data_quality": {"status": "ok|partial|error"},
                }
            },
        },
        "rules": [
            "Return only JSON, with no markdown fences or prose outside the JSON",
            "Only include sports requested in the sports array",
            f"Include at most {limit_per_sport} matches for each requested sport",
            "Group every result under grouped_by_sport using the sport key",
            "If a sport cannot be discovered, return an empty matches list plus an error string for that sport",
            "Use null for unknown kickoff, league, competition, notes, or source URLs",
            "Do not fabricate fixtures, kickoff times, leagues, or sources",
        ],
    }
    return json.dumps(payload, sort_keys=True)
