"""Tests for baseball sport module skeleton."""

from __future__ import annotations

from unittest.mock import MagicMock

from baseball_domain import (
    MLBBattingOrder,
    MLBBattingOrderSlot,
    MLBGame,
    MLBGameContext,
    MLBProbablePitcher,
    MLBPropLine,
)
import pytest

from baseball_module import BaseballDataQualityError, BaseballModule, _find_game
from pick_request import PickRequest
from pipeline_runner import PipelineRunner, PipelineResult
from sport_module import SportModule, SportModuleRegistry


class TestBaseballModuleProtocol:
    def test_baseball_module_satisfies_sport_module_protocol(self) -> None:
        module = BaseballModule()
        assert isinstance(module, SportModule)

    def test_sport_id_is_baseball(self) -> None:
        module = BaseballModule()
        assert module.sport_id == "baseball"

    def test_supported_markets(self) -> None:
        module = BaseballModule()
        expected = {"hits", "total_bases", "runs", "rbi", "home_runs", "strikeouts", "walks", "pitcher_outs"}
        assert module.supported_markets == expected

    def test_supported_leagues(self) -> None:
        module = BaseballModule()
        assert module.supported_leagues == {"mlb"}

    def test_npb_kbo_not_in_supported_leagues(self) -> None:
        module = BaseballModule()
        assert "npb" not in module.supported_leagues
        assert "kbo" not in module.supported_leagues


class TestBaseballModuleRegistry:
    def test_baseball_registers_in_sport_module_registry(self) -> None:
        registry = SportModuleRegistry()
        module = BaseballModule()
        registry.register(module)
        assert registry.get("baseball") is module

    def test_baseball_in_default_registry(self) -> None:
        from sport_module import get_sport_module

        module = get_sport_module("baseball")
        assert module.sport_id == "baseball"

    def test_baseball_does_not_conflict_with_other_sports(self) -> None:
        from basketball_module import BasketballModule
        from sport_module import SoccerModule

        registry = SportModuleRegistry()
        registry.register(SoccerModule())
        registry.register(BasketballModule())
        registry.register(BaseballModule())
        assert registry.get("soccer").sport_id == "soccer"
        assert registry.get("basketball").sport_id == "basketball"
        assert registry.get("baseball").sport_id == "baseball"


class TestBaseballDeterministicFallback:
    def test_default_collect_inputs_rejects_missing_live_service(self) -> None:
        module = BaseballModule()

        with pytest.raises(BaseballDataQualityError, match="Could not find enough match details"):
            module.collect_inputs(
                home_team="Yankees",
                away_team="Red Sox",
                match_date="2026-06-01",
                league="mlb",
            )

    def test_explicit_fallback_collect_inputs_returns_structured_data(self) -> None:
        module = BaseballModule(allow_deterministic_fallback=True)
        inputs = module.collect_inputs(
            home_team="Yankees",
            away_team="Red Sox",
            match_date="2026-06-01",
            league="mlb",
        )
        assert "home_team" in inputs
        assert "away_team" in inputs
        assert "players" in inputs
        assert len(inputs["players"]) > 0
        assert inputs["data_quality"]["source"] == "deterministic_fallback"

    def test_explicit_fallback_score_returns_valid_picks(self) -> None:
        module = BaseballModule(allow_deterministic_fallback=True)
        inputs = module.collect_inputs(
            home_team="Yankees",
            away_team="Red Sox",
            match_date="2026-06-01",
        )
        scores = module.score(inputs, markets=("hits", "total_bases"))
        assert len(scores) > 0
        for pick in scores:
            assert "player" in pick
            assert "market" in pick
            assert "score" in pick
            assert "line" in pick
            assert "direction" in pick
            assert "confidence" in pick
            assert pick["market"] in ("hits", "total_bases")

    def test_explicit_fallback_score_all_markets_when_none_specified(self) -> None:
        module = BaseballModule(allow_deterministic_fallback=True)
        inputs = module.collect_inputs(
            home_team="Yankees",
            away_team="Red Sox",
            match_date="2026-06-01",
        )
        scores = module.score(inputs)
        markets_seen = {s["market"] for s in scores}
        assert len(markets_seen) >= 2

    def test_explain_returns_nonempty_string(self) -> None:
        module = BaseballModule()
        pick = {
            "player": "Aaron Judge",
            "market": "home_runs",
            "direction": "over",
            "line": 0.5,
            "confidence": "medium",
            "score": 0.6,
        }
        explanation = module.explain(pick)
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "Aaron Judge" in explanation


class TestBaseballPipelineIntegration:
    def test_baseball_request_runs_through_pipeline(self) -> None:
        module = BaseballModule(allow_deterministic_fallback=True)
        request = PickRequest(
            sport="baseball",
            event_date="2026-06-01",
            home_team="Yankees",
            away_team="Red Sox",
            markets=("hits", "strikeouts"),
            league="mlb",
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)
        assert isinstance(result, PipelineResult)
        assert result.status == "success"
        assert len(result.scores) > 0


class TestBaseballModuleWithService:
    """With a real MLBCollectionService, collect_inputs fetches live data."""

    def _make_schedule_result(self):
        result = MagicMock()
        result.meta.available = True
        result.games = [
            {
                "gamePk": 717001,
                "teams": {
                    "home": {"team": {"id": 147, "name": "New York Yankees"}},
                    "away": {"team": {"id": 111, "name": "Boston Red Sox"}},
                },
                "gameDate": "2026-05-25T23:05:00Z",
                "venue": {"id": 3313, "name": "Yankee Stadium"},
                "status": {"detailedState": "Scheduled"},
            }
        ]
        return result

    def _make_game_context(self) -> MLBGameContext:
        game = MLBGame(
            event_id="717001",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            venue="Yankee Stadium",
            game_time_utc="2026-05-25T23:05:00Z",
            home_team_id=147,
            away_team_id=111,
            venue_id=3313,
        )
        home_order = MLBBattingOrder(
            team="New York Yankees",
            confirmed=True,
            slots=[
                MLBBattingOrderSlot(position=1, player_name="Anthony Volpe", player_id=683011, field_position="SS"),
                MLBBattingOrderSlot(position=2, player_name="Juan Soto", player_id=665742, field_position="RF"),
                MLBBattingOrderSlot(position=3, player_name="Aaron Judge", player_id=592450, field_position="DH"),
            ],
        )
        away_order = MLBBattingOrder(
            team="Boston Red Sox",
            confirmed=True,
            slots=[
                MLBBattingOrderSlot(position=1, player_name="Jarren Duran", player_id=680776, field_position="CF"),
                MLBBattingOrderSlot(position=2, player_name="Rafael Devers", player_id=646240, field_position="3B"),
            ],
        )
        return MLBGameContext(
            game=game,
            home_batting_order=home_order,
            away_batting_order=away_order,
            home_probable_pitcher=MLBProbablePitcher(player_name="Gerrit Cole", player_id=543037, confirmed=True),
            away_probable_pitcher=MLBProbablePitcher(player_name="Brayan Bello", player_id=678394, confirmed=True),
            prop_lines=[
                MLBPropLine(player_name="Anthony Volpe", market="hits", line=1.5),
                MLBPropLine(player_name="Juan Soto", market="hits", line=1.5),
                MLBPropLine(player_name="Aaron Judge", market="hits", line=1.5),
                MLBPropLine(player_name="Jarren Duran", market="hits", line=1.5),
                MLBPropLine(player_name="Rafael Devers", market="hits", line=1.5),
            ],
        )

    def test_collect_inputs_uses_service_players(self):
        service = MagicMock()
        service._schedule.get_schedule.return_value = self._make_schedule_result()
        service.collect.return_value = self._make_game_context()

        module = BaseballModule(collection_service=service)
        inputs = module.collect_inputs(
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            match_date="2026-05-25",
        )

        player_names = [p["player_name"] for p in inputs["players"]]
        assert "Anthony Volpe" in player_names
        assert "Aaron Judge" in player_names
        assert "Gerrit Cole" in player_names
        assert "Brayan Bello" in player_names

    def test_collect_inputs_includes_batting_order(self):
        service = MagicMock()
        service._schedule.get_schedule.return_value = self._make_schedule_result()
        service.collect.return_value = self._make_game_context()

        module = BaseballModule(collection_service=service)
        inputs = module.collect_inputs(
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            match_date="2026-05-25",
        )

        batters = [p for p in inputs["players"] if p["type"] == "batter"]
        volpe = next(p for p in batters if p["player_name"] == "Anthony Volpe")
        assert volpe["batting_order"] == 1
        assert volpe["position"] == "SS"

    def test_rejects_when_game_not_found_by_default(self, caplog):
        schedule_result = MagicMock()
        schedule_result.meta.available = True
        schedule_result.games = []

        service = MagicMock()
        service._schedule.get_schedule.return_value = schedule_result

        module = BaseballModule(collection_service=service)

        with pytest.raises(BaseballDataQualityError, match="Could not find enough match details"):
            module.collect_inputs(
                home_team="Fake Team",
                away_team="Other Team",
                match_date="2026-05-25",
            )
        assert "baseball_collection_rejected" in caplog.text
        assert "schedule_unavailable" in caplog.text

    def test_explicit_fallback_when_game_not_found(self):
        schedule_result = MagicMock()
        schedule_result.meta.available = True
        schedule_result.games = []

        service = MagicMock()
        service._schedule.get_schedule.return_value = schedule_result

        module = BaseballModule(collection_service=service, allow_deterministic_fallback=True)
        inputs = module.collect_inputs(
            home_team="Fake Team",
            away_team="Other Team",
            match_date="2026-05-25",
        )

        assert inputs["players"][0]["player_name"] == "Aaron Judge"
        assert inputs["data_quality"]["source"] == "deterministic_fallback"

    def test_rejects_on_schedule_error_by_default(self, caplog):
        service = MagicMock()
        service._schedule.get_schedule.side_effect = RuntimeError("network")

        module = BaseballModule(collection_service=service)

        with pytest.raises(BaseballDataQualityError, match="Could not find enough match details"):
            module.collect_inputs(
                home_team="Yankees",
                away_team="Red Sox",
                match_date="2026-05-25",
            )
        assert "baseball_collection_rejected" in caplog.text
        assert "network" in caplog.text

    def test_score_works_with_real_data(self):
        service = MagicMock()
        service._schedule.get_schedule.return_value = self._make_schedule_result()
        service.collect.return_value = self._make_game_context()

        module = BaseballModule(collection_service=service)
        inputs = module.collect_inputs(
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            match_date="2026-05-25",
        )
        scores = module.score(inputs, markets=("hits",))

        assert len(scores) > 0
        assert all(s["market"] == "hits" for s in scores)

    def test_pitcher_only_collection_rejects_hitter_markets(self, caplog):
        service = MagicMock()
        service._schedule.get_schedule.return_value = self._make_schedule_result()
        game = MLBGame(
            event_id="717001",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            venue="Yankee Stadium",
            game_time_utc="2026-05-25T23:05:00Z",
            home_team_id=147,
            away_team_id=111,
            venue_id=3313,
        )
        service.collect.return_value = MLBGameContext(
            game=game,
            home_probable_pitcher=MLBProbablePitcher(player_name="Gerrit Cole", player_id=543037, confirmed=True),
            away_probable_pitcher=MLBProbablePitcher(player_name="Brayan Bello", player_id=678394, confirmed=True),
            home_batting_order=MLBBattingOrder(team="New York Yankees", confirmed=False, slots=[]),
            away_batting_order=MLBBattingOrder(team="Boston Red Sox", confirmed=False, slots=[]),
        )

        module = BaseballModule(collection_service=service)
        inputs = module.collect_inputs(
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            match_date="2026-05-25",
        )

        assert inputs["collection_summary"]["game_found"] is True
        assert inputs["collection_summary"]["source"] == "mlb_statsapi"
        assert inputs["collection_summary"]["game_pk"] == "717001"
        assert inputs["collection_summary"]["batter_count"] == 0
        assert inputs["collection_summary"]["pitcher_count"] == 2
        assert inputs["collection_summary"]["prop_line_count"] == 0
        assert inputs["collection_summary"]["home_lineup_players"] == 0
        assert inputs["collection_summary"]["away_lineup_players"] == 0

        with pytest.raises(BaseballDataQualityError, match="MLB StatsAPI found the game") as exc_info:
            module.score(inputs, markets=("hits", "total_bases", "runs", "rbi", "home_runs"))
        assert exc_info.value.reason == "hitter_inputs_unavailable"
        assert "baseball_scoring_rejected" in caplog.text
        assert "hitter_inputs_unavailable" in caplog.text
        assert "source=mlb_statsapi" in caplog.text
        assert "game_pk=717001" in caplog.text
        assert "players=2" in caplog.text
        assert "batters=0" in caplog.text
        assert "pitchers=2" in caplog.text
        assert "prop_lines=0" in caplog.text
        assert "home_lineup_players=0" in caplog.text
        assert "away_lineup_players=0" in caplog.text

    def test_missing_lines_do_not_become_zero_line_recommendations(self, caplog):
        module = BaseballModule()
        inputs = {
            "home_team": "New York Yankees",
            "away_team": "Boston Red Sox",
            "match_date": "2026-05-25",
            "league": "mlb",
            "players": [
                {
                    "player_name": "Aaron Judge",
                    "player_type": "batter",
                    "team": "NYY",
                    "batting_order": 2,
                    "hits_per_game": 1.5,
                    "hits_last5_per_game": 1.6,
                }
            ],
            "lines": {"Aaron Judge": {}},
        }

        with pytest.raises(BaseballDataQualityError, match="missing prop lines"):
            module.score(inputs, markets=("hits",))
        assert "baseball_scoring_rejected" in caplog.text
        assert "missing_prop_lines" in caplog.text


class TestFindGame:
    """Tests for _find_game team name matching with abbreviations."""

    _GAMES = [
        {
            "gamePk": 717001,
            "teams": {
                "home": {"team": {"id": 119, "name": "Los Angeles Dodgers"}},
                "away": {"team": {"id": 115, "name": "Colorado Rockies"}},
            },
        },
        {
            "gamePk": 717002,
            "teams": {
                "home": {"team": {"id": 147, "name": "New York Yankees"}},
                "away": {"team": {"id": 111, "name": "Boston Red Sox"}},
            },
        },
    ]

    def test_full_name_match(self):
        result = _find_game(self._GAMES, "Los Angeles Dodgers", "Colorado Rockies")
        assert result is not None
        assert result["gamePk"] == 717001

    def test_abbreviation_lad(self):
        result = _find_game(self._GAMES, "lad", "col")
        assert result is not None
        assert result["gamePk"] == 717001

    def test_abbreviation_nyy(self):
        result = _find_game(self._GAMES, "nyy", "bos")
        assert result is not None
        assert result["gamePk"] == 717002

    def test_partial_name_dodgers(self):
        result = _find_game(self._GAMES, "dodgers", "rockies")
        assert result is not None
        assert result["gamePk"] == 717001

    def test_partial_name_yankees(self):
        result = _find_game(self._GAMES, "yankees", "red sox")
        assert result is not None
        assert result["gamePk"] == 717002

    def test_no_match_returns_none(self):
        result = _find_game(self._GAMES, "cubs", "mets")
        assert result is None

