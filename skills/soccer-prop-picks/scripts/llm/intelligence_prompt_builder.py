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
