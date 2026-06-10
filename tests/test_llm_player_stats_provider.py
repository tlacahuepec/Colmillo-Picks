"""Tests for basketball LLM player stats provider."""

from __future__ import annotations

import json

from tests.conftest import load_script_module


def _full_stats_response() -> dict:
    return {
        "players": [
            {
                "player_name": "LeBron James",
                "team": "LAL",
                "position": "SF",
                "minutes_proj": 35.0,
                "usage_rate": 0.28,
                "points_avg": 25.5,
                "points_last5": 27.0,
                "assist_avg": 7.2,
                "assist_last5": 7.8,
                "rebound_avg": 7.5,
                "rebound_last5": 8.0,
                "threes_avg": 2.3,
                "threes_last5": 2.5,
                "three_point_attempts": 5.5,
                "rotation_risk": "locked_in",
                "injury_status": "healthy",
                "is_starter": True,
            },
            {
                "player_name": "Anthony Davis",
                "team": "LAL",
                "position": "PF",
                "minutes_proj": 34.0,
                "usage_rate": 0.27,
                "points_avg": 24.0,
                "points_last5": 26.0,
                "assist_avg": 3.2,
                "assist_last5": 3.5,
                "rebound_avg": 10.5,
                "rebound_last5": 11.0,
                "threes_avg": 1.5,
                "threes_last5": 1.8,
                "three_point_attempts": 3.0,
                "rotation_risk": "normal",
                "injury_status": "healthy",
                "is_starter": True,
            },
            {
                "player_name": "Austin Reaves",
                "team": "LAL",
                "position": "SG",
                "minutes_proj": 32.0,
                "usage_rate": 0.22,
                "points_avg": 18.0,
                "points_last5": 20.0,
                "assist_avg": 5.0,
                "assist_last5": 5.5,
                "rebound_avg": 4.0,
                "rebound_last5": 4.5,
                "threes_avg": 2.0,
                "threes_last5": 2.2,
                "three_point_attempts": 5.0,
                "rotation_risk": "normal",
                "injury_status": "healthy",
                "is_starter": True,
            },
            {
                "player_name": "Jayson Tatum",
                "team": "BOS",
                "position": "SF",
                "minutes_proj": 36.0,
                "usage_rate": 0.30,
                "points_avg": 27.0,
                "points_last5": 29.0,
                "assist_avg": 4.5,
                "assist_last5": 5.0,
                "rebound_avg": 8.5,
                "rebound_last5": 8.0,
                "threes_avg": 3.0,
                "threes_last5": 3.5,
                "three_point_attempts": 8.0,
                "rotation_risk": "locked_in",
                "injury_status": "healthy",
                "is_starter": True,
            },
            {
                "player_name": "Jaylen Brown",
                "team": "BOS",
                "position": "SG",
                "minutes_proj": 34.0,
                "usage_rate": 0.26,
                "points_avg": 23.0,
                "points_last5": 22.0,
                "assist_avg": 3.5,
                "assist_last5": 3.0,
                "rebound_avg": 5.5,
                "rebound_last5": 5.5,
                "threes_avg": 2.0,
                "threes_last5": 2.2,
                "three_point_attempts": 5.5,
                "rotation_risk": "normal",
                "injury_status": "healthy",
                "is_starter": True,
            },
            {
                "player_name": "Derrick White",
                "team": "BOS",
                "position": "PG",
                "minutes_proj": 32.0,
                "usage_rate": 0.20,
                "points_avg": 15.5,
                "points_last5": 17.0,
                "assist_avg": 5.0,
                "assist_last5": 5.5,
                "rebound_avg": 4.0,
                "rebound_last5": 4.0,
                "threes_avg": 2.5,
                "threes_last5": 2.8,
                "three_point_attempts": 6.0,
                "rotation_risk": "normal",
                "injury_status": "healthy",
                "is_starter": True,
            },
        ]
    }


class TestLLMPlayerStatsProviderHappyPath:
    def test_maps_full_response_to_player_dicts(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return _full_stats_response()

        provider = module.LLMPlayerStatsProvider(client=_Client())
        result = provider.get_player_stats(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        assert result is not None
        assert len(result) == 6
        lebron = result[0]
        assert lebron["player_name"] == "LeBron James"
        assert lebron["team"] == "LAL"
        assert lebron["position"] == "SF"
        assert lebron["minutes_proj"] == 35.0
        assert lebron["usage_rate"] == 0.28
        assert lebron["points_avg"] == 25.5
        assert lebron["points_last5"] == 27.0
        assert lebron["assist_avg"] == 7.2
        assert lebron["rebound_avg"] == 7.5
        assert lebron["threes_avg"] == 2.3
        assert lebron["three_point_attempts"] == 5.5
        assert lebron["rotation_risk"] == "locked_in"
        assert lebron["is_starter"] is True

    def test_returns_three_players_per_team(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return _full_stats_response()

        provider = module.LLMPlayerStatsProvider(client=_Client())
        result = provider.get_player_stats(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        assert result is not None
        home_players = [p for p in result if p["team"] == "LAL"]
        away_players = [p for p in result if p["team"] == "BOS"]
        assert len(home_players) == 3
        assert len(away_players) == 3


class TestLLMPlayerStatsProviderPrompt:
    def test_system_prompt_mentions_basketball(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")
        prompt = module.LLMPlayerStatsProvider._build_system_prompt()
        assert "basketball" in prompt.lower() or "nba" in prompt.lower()

    def test_user_prompt_includes_teams_and_date(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")
        prompt = module.LLMPlayerStatsProvider._build_user_prompt(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        prompt_data = json.loads(prompt)
        assert prompt_data["request"]["home_team"] == "Lakers"
        assert prompt_data["request"]["away_team"] == "Celtics"
        assert prompt_data["request"]["match_date"] == "2026-06-01"

    def test_user_prompt_requests_per_player_stats(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")
        prompt = module.LLMPlayerStatsProvider._build_user_prompt(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        prompt_data = json.loads(prompt)
        shape = prompt_data["required_json_shape"]
        assert "players" in shape
        player_shape = shape["players"][0]
        assert "points_avg" in player_shape
        assert "minutes_proj" in player_shape
        assert "usage_rate" in player_shape
        assert "rotation_risk" in player_shape

    def test_user_prompt_includes_rules(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")
        prompt = module.LLMPlayerStatsProvider._build_user_prompt(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        prompt_data = json.loads(prompt)
        assert "rules" in prompt_data
        assert len(prompt_data["rules"]) > 0


class TestLLMPlayerStatsProviderFallback:
    def test_returns_none_on_exception(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                raise RuntimeError("LLM timeout")

        provider = module.LLMPlayerStatsProvider(client=_Client())
        result = provider.get_player_stats(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        assert result is None

    def test_partial_response_uses_safe_defaults(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return {
                    "players": [
                        {
                            "player_name": "LeBron James",
                            "team": "LAL",
                            "position": "SF",
                        }
                    ]
                }

        provider = module.LLMPlayerStatsProvider(client=_Client())
        result = provider.get_player_stats(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        assert result is not None
        assert len(result) == 1
        player = result[0]
        assert player["player_name"] == "LeBron James"
        assert player["minutes_proj"] is None
        assert player["usage_rate"] is None
        assert player["points_avg"] is None

    def test_empty_players_returns_none(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return {"players": []}

        provider = module.LLMPlayerStatsProvider(client=_Client())
        result = provider.get_player_stats(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        assert result is None


class TestLLMPlayerStatsProviderDebug:
    def test_debug_logs_response(self, monkeypatch, capsys) -> None:
        module = load_script_module("llm_player_stats_provider.py")
        monkeypatch.setenv("COLMILLO_PLAYER_STATS_LLM_DEBUG", "1")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return _full_stats_response()

        provider = module.LLMPlayerStatsProvider(client=_Client())
        provider.get_player_stats(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        stderr = capsys.readouterr().err
        assert "[player-stats-llm-debug] response:" in stderr

    def test_captures_last_sources(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")

        class _FakeSource:
            def __init__(self, url, title):
                self.url = url
                self.title = title

        class _ClientWithSources:
            def __init__(self):
                self.last_sources = [
                    _FakeSource("https://nba.com/stats", "NBA Stats"),
                ]

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return _full_stats_response()

        provider = module.LLMPlayerStatsProvider(client=_ClientWithSources())
        provider.get_player_stats(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )

        assert len(provider.last_sources) == 1
        assert provider.last_sources[0].url == "https://nba.com/stats"


class TestPromptRosterRules:
    def test_prompt_includes_current_roster_rule(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")
        prompt = module.LLMPlayerStatsProvider._build_user_prompt(
            home_team="Knicks", away_team="Spurs", match_date="2026-06-08",
        )
        prompt_data = json.loads(prompt)
        rules_text = " ".join(prompt_data["rules"]).lower()
        assert "current" in rules_text and "roster" in rules_text

    def test_prompt_includes_trade_exclusion_rule(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")
        prompt = module.LLMPlayerStatsProvider._build_user_prompt(
            home_team="Knicks", away_team="Spurs", match_date="2026-06-08",
        )
        prompt_data = json.loads(prompt)
        rules_text = " ".join(prompt_data["rules"]).lower()
        assert "traded" in rules_text or "waived" in rules_text or "released" in rules_text

    def test_prompt_requests_4_players_per_team(self) -> None:
        module = load_script_module("llm_player_stats_provider.py")
        prompt = module.LLMPlayerStatsProvider._build_user_prompt(
            home_team="Knicks", away_team="Spurs", match_date="2026-06-08",
        )
        prompt_data = json.loads(prompt)
        rules_text = " ".join(prompt_data["rules"])
        assert "4 from the home team" in rules_text
        assert "4 from the away team" in rules_text
