"""Unit tests for BasketballPropLinesAdapter."""


from basketball_prop_lines_adapter import BasketballPropLinesAdapter
from basketball_module import BasketballModule
from services.catalog.odds_provider import TheOddsApiAdapter, TheOddsApiConfig


def test_basketball_prop_lines_adapter_fetches_replay():
    adapter = BasketballPropLinesAdapter(provider=TheOddsApiAdapter(TheOddsApiConfig(api_key=None)))
    players = [
        {"player_name": "Shai Gilgeous-Alexander", "team": "OKC"},
        {"player_name": "Tyrese Haliburton", "team": "IND"},
    ]
    lines = adapter.get_prop_lines(
        players=players,
        markets=("points", "assists", "rebounds", "threes"),
    )
    assert lines is not None
    assert "Shai Gilgeous-Alexander" in lines
    assert "Tyrese Haliburton" in lines

    sga = lines["Shai Gilgeous-Alexander"]
    assert sga["points"]["line"] == 30.5
    assert sga["rebounds"]["line"] == 5.5
    assert sga["assists"]["line"] == 6.5

    hali = lines["Tyrese Haliburton"]
    assert hali["points"]["line"] == 18.5
    assert hali["assists"]["line"] == 9.5
    assert hali["threes"]["line"] == 2.5


def test_basketball_prop_lines_adapter_empty_players():
    adapter = BasketballPropLinesAdapter()
    lines = adapter.get_prop_lines(players=[], markets=("points",))
    assert lines == {}


def test_basketball_module_scores_with_prop_lines_adapter():
    adapter = BasketballPropLinesAdapter(provider=TheOddsApiAdapter(TheOddsApiConfig(api_key=None)))
    players = [
        {
            "player_name": "Shai Gilgeous-Alexander",
            "team": "OKC",
            "position": "PG",
            "minutes_proj": 36.0,
            "usage_rate": 0.32,
            "points_avg": 31.0,
            "points_last5": 33.0,
            "assist_avg": 6.2,
            "assist_last5": 7.0,
            "rebound_avg": 5.5,
            "rebound_last5": 6.0,
            "threes_avg": 1.8,
            "threes_last5": 2.0,
            "three_point_attempts": 4.5,
            "rotation_risk": "locked_in",
            "is_starter": True,
        },
        {
            "player_name": "Tyrese Haliburton",
            "team": "IND",
            "position": "PG",
            "minutes_proj": 35.0,
            "usage_rate": 0.25,
            "points_avg": 19.5,
            "points_last5": 21.0,
            "assist_avg": 10.5,
            "assist_last5": 11.0,
            "rebound_avg": 4.0,
            "rebound_last5": 4.5,
            "threes_avg": 2.8,
            "threes_last5": 3.0,
            "three_point_attempts": 7.5,
            "rotation_risk": "locked_in",
            "is_starter": True,
        },
    ]

    fetched_lines = adapter.get_prop_lines(players=players, markets=("points", "assists", "threes"))
    assert fetched_lines is not None

    match_inputs = {
        "home_team": "Oklahoma City Thunder",
        "away_team": "Indiana Pacers",
        "match_date": "2025-06-05",
        "league": "nba",
        "players": players,
        "lines": fetched_lines,
        "game": {},
    }

    module = BasketballModule(props_provider=adapter)
    scores = module.score(match_inputs, markets=("points", "assists", "threes"))
    assert len(scores) > 0
    scored_players = {s["player"] for s in scores}
    assert "Shai Gilgeous-Alexander" in scored_players
    assert "Tyrese Haliburton" in scored_players
