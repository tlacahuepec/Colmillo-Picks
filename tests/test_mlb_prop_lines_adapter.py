"""Unit tests for MLBPropLinesAdapter and its integration into MLBCollectionService."""

from unittest.mock import MagicMock


from baseball_domain import (
    MLBGame,
    MLBGameContext,
    MLBProbablePitcher,
    MLBPropLine,
    MLBBattingOrder,
    MLBBattingOrderSlot,
)
from mlb_prop_lines_adapter import MLBPropLinesAdapter
from mlb_provider_ports import (
    BallparkResult,
    BullpenResult,
    MLBLineupsResult,
    MLBPropLinesPort,
    MLBProviderMeta,
    MLBWeatherResult,
    ProbablePitcherResult,
)
from mlb_collection import MLBCollectionService
from baseball_module import BaseballModule, _context_to_scoring_input
from services.catalog.odds_provider import TheOddsApiAdapter, TheOddsApiConfig


def test_mlb_prop_lines_adapter_conforms_to_port():
    adapter = MLBPropLinesAdapter()
    assert isinstance(adapter, MLBPropLinesPort)


def test_mlb_prop_lines_adapter_fetches_replay_props():
    adapter = MLBPropLinesAdapter(provider=TheOddsApiAdapter(TheOddsApiConfig(api_key=None)))
    res = adapter.get_prop_lines(
        game_pk=12345,
        home_team="New York Yankees",
        away_team="Boston Red Sox",
        date="2025-05-24",
    )
    assert res.meta.available is True
    assert len(res.prop_lines) > 0
    judge_lines = [p for p in res.prop_lines if p.player_name == "Aaron Judge"]
    assert len(judge_lines) > 0
    markets = {p.market for p in judge_lines}
    assert "hits" in markets
    assert "home_runs" in markets
    assert "total_bases" in markets


def test_mlb_collection_service_populates_prop_lines():
    mock_schedule = MagicMock()
    mock_pitchers = MagicMock()
    mock_pitchers.get_probable_pitchers.return_value = ProbablePitcherResult(
        meta=MLBProviderMeta(available=True),
        home_pitcher={"id": 1, "fullName": "Gerrit Cole", "confirmed": True},
        away_pitcher={"id": 2, "fullName": "Tanner Houck", "confirmed": True},
    )
    mock_lineups = MagicMock()
    mock_lineups.get_lineups.return_value = MLBLineupsResult(
        meta=MLBProviderMeta(available=True),
        confirmed=True,
        home_order=[{"id": 10, "fullName": "Aaron Judge", "position": "RF"}],
        away_order=[{"id": 20, "fullName": "Rafael Devers", "position": "3B"}],
    )
    mock_player_stats = MagicMock()
    mock_splits = MagicMock()
    mock_bullpen = MagicMock()
    mock_bullpen.get_bullpen_state.return_value = BullpenResult(meta=MLBProviderMeta(available=True), arms=[])
    mock_weather = MagicMock()
    mock_weather.get_weather.return_value = MLBWeatherResult(meta=MLBProviderMeta(available=True), temp_f=72)
    mock_ballpark = MagicMock()
    mock_ballpark.get_ballpark.return_value = BallparkResult(meta=MLBProviderMeta(available=True), park_factor=1.0)

    prop_adapter = MLBPropLinesAdapter(provider=TheOddsApiAdapter(TheOddsApiConfig(api_key=None)))

    service = MLBCollectionService(
        schedule=mock_schedule,
        pitchers=mock_pitchers,
        lineups=mock_lineups,
        player_stats=mock_player_stats,
        splits=mock_splits,
        bullpen=mock_bullpen,
        weather=mock_weather,
        ballpark=mock_ballpark,
        prop_lines=prop_adapter,
    )

    game = MLBGame(
        event_id="12345",
        home_team="New York Yankees",
        away_team="Boston Red Sox",
        venue="Yankee Stadium",
        game_time_utc="2025-05-24T17:05:00Z",
        home_team_id=147,
        away_team_id=111,
        venue_id=3313,
    )

    ctx = service.collect(game_pk=12345, game=game)
    assert len(ctx.prop_lines) > 0
    assert any(p.player_name == "Aaron Judge" for p in ctx.prop_lines)
    assert any(p.player_name == "Gerrit Cole" for p in ctx.prop_lines)


def test_baseball_module_scores_with_prop_lines_without_rejection():
    # Construct context directly as done in live collection
    game = MLBGame(
        event_id="12345",
        home_team="New York Yankees",
        away_team="Boston Red Sox",
        venue="Yankee Stadium",
        game_time_utc="2025-05-24T17:05:00Z",
    )
    home_order = MLBBattingOrder(
        team="New York Yankees",
        confirmed=True,
        slots=[
            MLBBattingOrderSlot(position=1, player_name="Aaron Judge", field_position="RF"),
            MLBBattingOrderSlot(position=2, player_name="Juan Soto", field_position="LF"),
        ],
    )
    away_order = MLBBattingOrder(
        team="Boston Red Sox",
        confirmed=True,
        slots=[
            MLBBattingOrderSlot(position=1, player_name="Rafael Devers", field_position="3B"),
        ],
    )
    home_pitcher = MLBProbablePitcher(player_name="Gerrit Cole", confirmed=True)
    away_pitcher = MLBProbablePitcher(player_name="Tanner Houck", confirmed=True)

    prop_lines = [
        MLBPropLine(player_name="Aaron Judge", market="hits", line=1.5, over_odds=-140, under_odds=110),
        MLBPropLine(player_name="Aaron Judge", market="total_bases", line=2.5, over_odds=105, under_odds=-135),
        MLBPropLine(player_name="Juan Soto", market="hits", line=1.5, over_odds=-145, under_odds=115),
        MLBPropLine(player_name="Gerrit Cole", market="strikeouts", line=7.5, over_odds=-115, under_odds=-115),
        MLBPropLine(player_name="Rafael Devers", market="hits", line=1.5, over_odds=-135, under_odds=105),
    ]

    ctx = MLBGameContext(
        game=game,
        home_probable_pitcher=home_pitcher,
        away_probable_pitcher=away_pitcher,
        home_batting_order=home_order,
        away_batting_order=away_order,
        prop_lines=prop_lines,
    )

    players, lines = _context_to_scoring_input(ctx)
    match_inputs = {
        "home_team": "New York Yankees",
        "away_team": "Boston Red Sox",
        "match_date": "2025-05-24",
        "league": "mlb",
        "players": players,
        "lines": lines,
    }

    module = BaseballModule()
    scores = module.score(match_inputs, markets=("hits", "strikeouts"))
    assert len(scores) > 0
    scored_players = {s["player"] for s in scores}
    assert "Aaron Judge" in scored_players
    assert "Gerrit Cole" in scored_players
