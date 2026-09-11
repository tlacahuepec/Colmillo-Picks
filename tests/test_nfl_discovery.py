from datetime import datetime, timezone

import pytest

from match_discovery import MatchDiscoveryError, _normalize_sport_result


def test_nfl_uses_local_kickoff_date_and_excludes_started_or_unknown(monkeypatch):
    import match_discovery

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 10, 23, 30, tzinfo=timezone.utc)

    monkeypatch.setattr(match_discovery, "datetime", Clock)
    raw = {
        "grouped_by_sport": {
            "nfl": {
                "matches": [
                    {
                        "home_team": "A",
                        "away_team": "B",
                        "event_date": "2026-09-11",
                        "league": "nfl",
                        "kickoff_utc": "2026-09-11T00:30:00Z",
                    },
                    {
                        "home_team": "A",
                        "away_team": "B",
                        "event_date": "2026-09-10",
                        "league": "nfl",
                        "kickoff_utc": "2026-09-10T23:29:00Z",
                    },
                    {
                        "home_team": "A",
                        "away_team": "B",
                        "event_date": "2026-09-10",
                        "league": "nfl",
                    },
                ]
            }
        }
    }
    result = _normalize_sport_result(
        raw=raw,
        sport="nfl",
        date_utc="2026-09-10",
        limit_per_sport=5,
        timezone="America/Chicago",
    )
    assert len(result["matches"]) == 1
    assert result["matches"][0]["event_date"] == "2026-09-10"


def test_invalid_nfl_timezone_is_a_discovery_error():
    with pytest.raises(MatchDiscoveryError, match="timezone"):
        _normalize_sport_result(
            raw={},
            sport="nfl",
            date_utc="2026-09-10",
            limit_per_sport=1,
            timezone="Invalid/Timezone",
        )
