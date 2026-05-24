"""Tests for basketball LLM prop lines provider."""

from __future__ import annotations

import json

from tests.conftest import load_script_module


def _full_props_response() -> dict:
    return {
        "players": {
            "LeBron James": {
                "points": [
                    {"source": "PrizePicks", "line": 25.5},
                    {"source": "DraftKings", "line": 25.5},
                    {"source": "FanDuel", "line": 26.0},
                ],
                "assists": [
                    {"source": "PrizePicks", "line": 7.5},
                    {"source": "DraftKings", "line": 7.5},
                    {"source": "FanDuel", "line": 7.5},
                ],
                "rebounds": [
                    {"source": "PrizePicks", "line": 7.5},
                    {"source": "DraftKings", "line": 8.0},
                    {"source": "FanDuel", "line": 7.5},
                ],
                "threes": [
                    {"source": "PrizePicks", "line": 2.5},
                    {"source": "DraftKings", "line": 2.5},
                    {"source": "FanDuel", "line": 2.5},
                ],
            },
            "Jayson Tatum": {
                "points": [
                    {"source": "PrizePicks", "line": 27.5},
                    {"source": "DraftKings", "line": 27.5},
                    {"source": "FanDuel", "line": 28.0},
                ],
                "assists": [
                    {"source": "PrizePicks", "line": 4.5},
                    {"source": "DraftKings", "line": 4.5},
                    {"source": "FanDuel", "line": 5.0},
                ],
                "rebounds": [
                    {"source": "PrizePicks", "line": 8.5},
                    {"source": "DraftKings", "line": 8.5},
                    {"source": "FanDuel", "line": 8.5},
                ],
                "threes": [
                    {"source": "PrizePicks", "line": 3.5},
                    {"source": "DraftKings", "line": 3.5},
                    {"source": "FanDuel", "line": 3.0},
                ],
            },
        }
    }


class TestLLMPropsProviderHappyPath:
    def test_maps_response_to_player_lines(self) -> None:
        module = load_script_module("llm_props_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return _full_props_response()

        provider = module.LLMPropsProvider(client=_Client())
        result = provider.get_prop_lines(
            players=[{"player_name": "LeBron James"}, {"player_name": "Jayson Tatum"}],
            markets=("points", "assists", "rebounds", "threes"),
        )

        assert result is not None
        assert "LeBron James" in result
        assert "Jayson Tatum" in result
        lebron = result["LeBron James"]
        assert "points" in lebron
        assert lebron["points"]["line"] == 25.5
        assert lebron["points"]["market_agreement"] > 0.9
        assert len(lebron["points"]["sources"]) == 3

    def test_market_agreement_high_when_books_agree(self) -> None:
        module = load_script_module("llm_props_provider.py")
        agreement = module.LLMPropsProvider._compute_market_agreement([25.5, 25.5, 25.5])
        assert agreement == 1.0

    def test_market_agreement_lower_when_books_diverge(self) -> None:
        module = load_script_module("llm_props_provider.py")
        agreement = module.LLMPropsProvider._compute_market_agreement([20.0, 25.0, 30.0])
        assert agreement < 0.85

    def test_market_agreement_zero_lines_returns_zero(self) -> None:
        module = load_script_module("llm_props_provider.py")
        agreement = module.LLMPropsProvider._compute_market_agreement([])
        assert agreement == 0.0

    def test_consensus_line_is_median(self) -> None:
        module = load_script_module("llm_props_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return {
                    "players": {
                        "Test Player": {
                            "points": [
                                {"source": "A", "line": 20.0},
                                {"source": "B", "line": 25.0},
                                {"source": "C", "line": 30.0},
                            ]
                        }
                    }
                }

        provider = module.LLMPropsProvider(client=_Client())
        result = provider.get_prop_lines(
            players=[{"player_name": "Test Player"}],
            markets=("points",),
        )

        assert result is not None
        assert result["Test Player"]["points"]["line"] == 25.0


class TestLLMPropsProviderPrompt:
    def test_system_prompt_mentions_prop_lines(self) -> None:
        module = load_script_module("llm_props_provider.py")
        prompt = module.LLMPropsProvider._build_system_prompt()
        assert "prop" in prompt.lower() or "lines" in prompt.lower()

    def test_user_prompt_includes_player_names(self) -> None:
        module = load_script_module("llm_props_provider.py")
        prompt = module.LLMPropsProvider._build_user_prompt(
            players=[{"player_name": "LeBron James"}, {"player_name": "Jayson Tatum"}],
            markets=("points", "assists"),
        )
        prompt_data = json.loads(prompt)
        assert "LeBron James" in prompt_data["request"]["players"]
        assert "Jayson Tatum" in prompt_data["request"]["players"]

    def test_user_prompt_includes_markets(self) -> None:
        module = load_script_module("llm_props_provider.py")
        prompt = module.LLMPropsProvider._build_user_prompt(
            players=[{"player_name": "LeBron James"}],
            markets=("points", "assists", "rebounds"),
        )
        prompt_data = json.loads(prompt)
        assert "points" in prompt_data["request"]["markets"]
        assert "assists" in prompt_data["request"]["markets"]
        assert "rebounds" in prompt_data["request"]["markets"]

    def test_user_prompt_includes_rules(self) -> None:
        module = load_script_module("llm_props_provider.py")
        prompt = module.LLMPropsProvider._build_user_prompt(
            players=[{"player_name": "LeBron James"}],
            markets=("points",),
        )
        prompt_data = json.loads(prompt)
        assert "rules" in prompt_data
        assert len(prompt_data["rules"]) > 0


class TestLLMPropsProviderFallback:
    def test_returns_none_on_exception(self) -> None:
        module = load_script_module("llm_props_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                raise RuntimeError("timeout")

        provider = module.LLMPropsProvider(client=_Client())
        result = provider.get_prop_lines(
            players=[{"player_name": "LeBron James"}],
            markets=("points",),
        )
        assert result is None

    def test_returns_none_on_empty_players(self) -> None:
        module = load_script_module("llm_props_provider.py")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return {"players": {}}

        provider = module.LLMPropsProvider(client=_Client())
        result = provider.get_prop_lines(
            players=[{"player_name": "LeBron James"}],
            markets=("points",),
        )
        assert result is None


class TestLLMPropsProviderDebug:
    def test_debug_logs_response(self, monkeypatch, capsys) -> None:
        module = load_script_module("llm_props_provider.py")
        monkeypatch.setenv("COLMILLO_PROPS_LLM_DEBUG", "1")

        class _Client:
            last_sources: list = []

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return _full_props_response()

        provider = module.LLMPropsProvider(client=_Client())
        provider.get_prop_lines(
            players=[{"player_name": "LeBron James"}],
            markets=("points",),
        )

        stderr = capsys.readouterr().err
        assert "[props-llm-debug] response:" in stderr

    def test_captures_last_sources(self) -> None:
        module = load_script_module("llm_props_provider.py")

        class _FakeSource:
            def __init__(self, url, title):
                self.url = url
                self.title = title

        class _ClientWithSources:
            def __init__(self):
                self.last_sources = [
                    _FakeSource("https://prizepicks.com", "PrizePicks"),
                ]

            def generate_structured(self, *, system_prompt, user_prompt, schema):
                return _full_props_response()

        provider = module.LLMPropsProvider(client=_ClientWithSources())
        provider.get_prop_lines(
            players=[{"player_name": "LeBron James"}],
            markets=("points",),
        )

        assert len(provider.last_sources) == 1
        assert provider.last_sources[0].url == "https://prizepicks.com"
