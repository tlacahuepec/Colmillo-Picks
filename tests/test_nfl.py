from copy import deepcopy
from datetime import datetime, timezone

import pytest

from nfl_module import NflModule
from nfl_scoring import score_nfl
from nfl_domain import NFL_MARKETS, valid_offer
from pick_request import PickRequest, validate_pick_request
from slate_ranking import candidate_from_pick


NOW = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)


def context():
    return {
        "game": {
            "home_team": "Kansas City Chiefs",
            "away_team": "Buffalo Bills",
            "event_date": "2026-09-10",
            "kickoff_utc": "2026-09-11T00:00:00Z",
            "status": "scheduled",
            "season_type": "regular",
            "season": 2026,
            "source_urls": ["https://www.nfl.com/schedules/"],
        },
        "players": [
            {
                "player_name": "Test QB",
                "team": "Kansas City Chiefs",
                "position": "QB",
                "injury_status": "active",
                "source_urls": ["https://www.nfl.com/stats/"],
                "opportunity_ratio": 1.1,
                "opponent_factor": 1.05,
                "game_logs": [
                    {
                        "date": f"2026-08-{day:02d}",
                        "season": 2026,
                        "played": True,
                        "season_type": "regular",
                        "passing_yards": 300,
                        "passing_touchdowns": 3,
                        "interceptions_thrown": 0,
                        "rushing_yards": 40,
                        "receiving_yards": 50,
                        "receptions": 5,
                        "scorer_touchdowns": 1,
                    }
                    for day in (1, 8, 15, 22, 29)
                ],
            }
        ],
        "teams": [
            {
                "team": name,
                "source_urls": ["https://www.nfl.com/stats/"],
                "points_for_avg": pf,
                "points_against_avg": pa,
                "points_for_last5": pf,
                "points_against_last5": pa,
                "games_played": 5,
                "season": 2026,
                "qb_status": "active",
                "rest_days": 7,
            }
            for name, pf, pa in [
                ("Kansas City Chiefs", 30, 17),
                ("Buffalo Bills", 20, 24),
            ]
        ],
        "weather": {"wind_kph": 5, "roof_closed": False},
        "offers": [],
        "exclusions": [],
    }


def offer(market="passing_yards", **updates):
    game = market in {"moneyline", "spread", "total"}
    item = {
        "market": market,
        "subject_name": "Kansas City Chiefs" if game else "Test QB",
        "selection": "home" if game else "over",
        "line": 250.5,
        "sportsbook": "Test Book",
        "odds_decimal": 1.91,
        "source_url": "https://sportsbook.example/nfl/game",
        "observed_at": NOW.isoformat(),
        "period": "full_game",
        "includes_overtime": True,
        "is_live": False,
        "is_primary": True,
    }
    if market in {"moneyline", "anytime_touchdown"}:
        item["line"] = None
    if market == "anytime_touchdown":
        item["selection"] = "yes"
    if market == "total":
        item.update(
            subject_name="Kansas City Chiefs v Buffalo Bills",
            selection="under",
            line=65.5,
        )
    if market == "spread":
        item["line"] = 0
    item.update(updates)
    return item


@pytest.mark.parametrize("market", sorted(NFL_MARKETS))
def test_markets_end_to_end(market):
    data = context()
    line = {
        "passing_touchdowns": 1.5,
        "interceptions_thrown": 0.5,
        "rushing_yards": 20.5,
        "receiving_yards": 20.5,
        "receptions": 2.5,
    }
    data["offers"] = [
        offer(market, **({"line": line[market]} if market in line else {}))
    ]
    if market == "interceptions_thrown":
        data["offers"][0]["selection"] = "under"
    picks = score_nfl(data, now=NOW)
    assert len(picks) == 1
    assert picks[0]["market"] == market
    assert picks[0]["offer"] == data["offers"][0]
    assert picks[0]["subject_name"]
    assert 0 <= picks[0]["score"] <= 1


@pytest.mark.parametrize(
    "updates",
    [
        {"source_url": ""},
        {"odds_decimal": float("nan")},
        {"is_live": True},
        {"is_primary": False},
        {"odds_decimal": 1},
        {"line": None},
        {"period": "first_half"},
        {"observed_at": "2025-01-01T00:00:00Z"},
        {"observed_at": "2099-01-01T00:00:00Z"},
    ],
)
def test_bad_offers_are_excluded(updates):
    assert not valid_offer(offer(**updates), now=NOW)


def test_best_offer_preserves_book_and_line():
    data = context()
    data["offers"] = [
        offer(),
        offer(sportsbook="Better Book", odds_decimal=2.1),
        offer(selection="under"),
    ]
    picks = score_nfl(data, now=NOW)
    assert len(picks) == 1
    assert picks[0]["offer"]["sportsbook"] == "Better Book"
    assert picks[0]["line"] == 250.5


@pytest.mark.parametrize(
    "change", ["inactive", "missing_stats", "started", "preseason", "wrong_team"]
)
def test_no_picks_for_ineligible_inputs(change):
    data = context()
    data["offers"] = [offer()]
    if change == "inactive":
        data["players"][0]["injury_status"] = "out"
    elif change == "missing_stats":
        data["players"][0]["game_logs"] = []
    elif change == "started":
        data["game"]["kickoff_utc"] = NOW.isoformat()
    elif change == "wrong_team":
        data["players"][0]["team"] = "Miami Dolphins"
    else:
        data["game"]["season_type"] = "preseason"
    assert score_nfl(data, now=NOW) == []
    assert data["exclusions"]


def test_byes_and_prior_season_samples():
    data = context()
    player = data["players"][0]
    player["game_logs"] = [
        dict(player["game_logs"][0], season=2025, date="2025-12-01"),
        {"date": "2026-09-01", "played": False, "passing_yards": 0},
    ]
    data["offers"] = [offer()]
    pick = score_nfl(data, now=NOW)[0]
    flags = pick["explainability"]["risk_flags"]
    assert "prior_season_data" in flags and "small_sample" in flags
    assert pick["confidence"] == "low"
    assert pick["data_quality"]["status"] == "prior_season_only"


def test_collection_failure_is_explicit_without_samples():
    module = NflModule(
        collector=lambda **kwargs: (_ for _ in ()).throw(ValueError("unavailable"))
    )
    from nfl_module import NflDataQualityError
    import pytest
    with pytest.raises(NflDataQualityError) as raised:
        module.collect_inputs(home_team="KC", away_team="BUF", match_date="2026-09-10")
    assert isinstance(raised.value.__cause__, ValueError)
    assert raised.value.reason["exception_type"] == "ValueError"


def test_request_and_slate_subject_contract():
    validate_pick_request(
        PickRequest(
            sport="nfl",
            league="nfl",
            event_date="2026-09-10",
            home_team="KC",
            away_team="BUF",
            markets=("moneyline",),
        )
    )
    data = context()
    data["offers"] = [offer("moneyline")]
    pick = score_nfl(deepcopy(data), now=NOW)[0]
    candidate = candidate_from_pick(pick, sport="nfl")
    assert candidate.subject_type == "team"
    assert candidate.subject_name == "Kansas City Chiefs"
    assert candidate.line is None


def test_preseason_logs_do_not_influence_regular_season_picks():
    data = context()
    data["offers"] = [offer()]
    for log in data["players"][0]["game_logs"]:
        log["season_type"] = "preseason"
    assert score_nfl(data, now=NOW) == []


def test_passing_td_does_not_count_as_anytime_scorer():
    data = context()
    for log in data["players"][0]["game_logs"]:
        log["passing_touchdowns"] = 4
        log["scorer_touchdowns"] = 0
    data["offers"] = [offer("passing_touchdowns", line=2.5), offer("anytime_touchdown")]
    assert [p["market"] for p in score_nfl(data, now=NOW)] == ["passing_touchdowns"]


def test_spread_uses_selected_team_signed_line():
    data = context()
    data["offers"] = [
        offer("spread", selection="away", subject_name="Buffalo Bills", line=14),
        offer("spread", selection="away", subject_name="Buffalo Bills", line=-14),
    ]
    picks = score_nfl(data, now=NOW)
    assert len(picks) == 1 and picks[0]["line"] == 14
    assert picks[0]["subject_name"] == "Buffalo Bills"


def test_wrong_game_total_is_rejected():
    data = context()
    data["offers"] = [offer("total", subject_name="Other teams")]
    assert score_nfl(data, now=NOW) == []


def test_injury_status_is_case_insensitive():
    data = context()
    data["players"][0]["injury_status"] = "Out"
    data["offers"] = [offer()]
    assert score_nfl(data, now=NOW) == []


def test_negative_rushing_yards_are_valid_game_stats():
    data = context()
    for log in data["players"][0]["game_logs"]:
        log["rushing_yards"] = -2
    data["offers"] = [offer("rushing_yards", line=0.5, selection="under")]
    picks = score_nfl(data, now=NOW)
    assert len(picks) == 1 and picks[0]["projection"] == -2
def test_resolve_team_accepts_city_only_aliases():
    from nfl_domain import resolve_team

    assert resolve_team("new orleans") == "New Orleans Saints"
    assert resolve_team("detroit") == "Detroit Lions"
