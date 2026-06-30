from __future__ import annotations

import json

from tests.conftest import load_script_module


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.status = 200

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _config():
    provider_config = load_script_module("provider_config.py")
    return provider_config.LLMFixtureProviderConfig(
        provider="openai-compatible",
        api_key="fixture-key",
        base_url="https://llm.example.test/v1",
        model="fixture-model",
    )


def test_llm_fixture_provider_maps_chat_completion_json_to_fixture() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "match_found": True,
                                    "confidence": "high",
                                    "match_id": "llm-fixture-123",
                                    "competition": "Premier League",
                                    "competition_type": "league",
                                    "is_elimination": False,
                                    "overtime_possible": False,
                                    "kickoff_utc": "2026-05-03T15:30:00+00:00",
                                    "venue": {
                                        "name": "Emirates Stadium",
                                        "city": "London",
                                        "country": "England",
                                    },
                                    "teams": {
                                        "home": {"team_id": "ARS", "team_name": "Arsenal"},
                                        "away": {"team_id": "LIV", "team_name": "Liverpool"},
                                    },
                                    "status": {"long": "Not Started", "short": "NS"},
                                }
                            )
                        }
                    }
                ]
            }
        )

    provider = module.LLMFixtureProvider(config=_config(), urlopen_fn=fake_urlopen, timeout_seconds=7)

    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Arsenal",
            away_team="Liverpool",
            match_date="2026-05-03",
            competition="Premier League",
        )
    )

    assert fixture == {
        "match_id": "llm-fixture-123",
        "competition": "Premier League",
        "competition_type": "league",
        "is_elimination": False,
        "overtime_possible": False,
        "kickoff_utc": "2026-05-03T15:30:00Z",
        "venue": {"name": "Emirates Stadium", "city": "London", "country": "England"},
        "teams": {
            "home": {"team_id": "ARS", "team_name": "Arsenal"},
            "away": {"team_id": "LIV", "team_name": "Liverpool"},
        },
        "status": {"long": "Not Started", "short": "NS"},
    }
    assert captured["url"] == "https://llm.example.test/v1/chat/completions"
    assert captured["timeout"] == 7
    body = captured["body"]
    assert body["model"] == "fixture-model"
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["role"] == "system"


def test_llm_fixture_provider_returns_none_when_match_not_verified() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {"match_found": False, "reason": "not verified"}

    provider = module.LLMFixtureProvider(config=_config(), client=_Client())

    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Arsenal",
            away_team="Liverpool",
            match_date="2026-05-03",
            competition="Premier League",
        )
    )

    assert fixture is None


def test_llm_fixture_provider_uses_safe_defaults_for_partial_fixture_json() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {
                "match_found": True,
                "competition": "Premier League",
                "teams": {
                    "home": {"team_name": "Arsenal"},
                    "away": {"team_name": "Liverpool"},
                },
                "venue": {},
            }

    provider = module.LLMFixtureProvider(config=_config(), client=_Client())

    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Arsenal",
            away_team="Liverpool",
            match_date="2026-05-03",
            competition="Premier League",
        )
    )

    assert fixture is not None
    assert fixture["match_id"] == "llm-premier-league-arsenal-liverpool-2026-05-03"
    assert fixture["teams"]["home"]["team_id"] == "ARS"
    assert fixture["teams"]["away"]["team_id"] == "LIV"
    assert fixture["venue"] == {"name": "Unknown Venue", "city": "Unknown", "country": "Unknown"}


def test_llm_fixture_provider_debug_logs_request_and_response(monkeypatch, capsys) -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")
    monkeypatch.setenv("COLMILLO_FIXTURE_LLM_DEBUG", "1")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {
                "match_found": True,
                "competition": "Bundesliga",
                "teams": {
                    "home": {"team_name": "Bayern Munich"},
                    "away": {"team_name": "VfB Stuttgart"},
                },
                "venue": {},
            }

    provider = module.LLMFixtureProvider(config=_config(), client=_Client())
    provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Bayern Munich",
            away_team="VfB Stuttgart",
            match_date="2026-05-23",
            competition="Bundesliga",
        )
    )

    stderr = capsys.readouterr().err
    assert "[fixture-llm-debug] request:" in stderr
    assert "[fixture-llm-debug] response:" in stderr
    assert "Bayern Munich" in stderr


def test_llm_fixture_provider_debug_logs_reason_when_match_not_found(monkeypatch, capsys) -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")
    monkeypatch.setenv("COLMILLO_FIXTURE_LLM_DEBUG", "1")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {
                "match_found": False,
                "reason": "Could not verify fixture for requested date.",
            }

    provider = module.LLMFixtureProvider(config=_config(), client=_Client())
    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Bayern Munich",
            away_team="VfB Stuttgart",
            match_date="2026-05-23",
            competition="Bundesliga",
        )
    )

    assert fixture is None
    stderr = capsys.readouterr().err
    assert "[fixture-llm-debug] match_not_found:" in stderr
    assert "Could not verify fixture for requested date." in stderr


def test_llm_fixture_provider_soft_accepts_high_confidence_team_date_match() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {
                "match_found": False,
                "confidence": "high",
                "match_id": "STUTTGART_BAYERN_2026-05-23",
                "competition": "Bundesliga",
                "competition_type": "league",
                "kickoff_utc": None,
                "teams": {
                    "home": {"team_id": "BAYERN_MUNICH", "team_name": "Bayern Munich"},
                    "away": {"team_id": "VfB_STUTTGART", "team_name": "VfB Stuttgart"},
                },
                "status": {"long": "Not Started", "short": "NS"},
                "venue": {"name": None, "city": None, "country": None},
            }

    provider = module.LLMFixtureProvider(config=_config(), client=_Client())
    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Bayern Munich",
            away_team="Vfb Stuttgart",
            match_date="2026-05-23",
            competition="League",
        )
    )

    assert fixture is not None
    assert fixture["teams"]["home"]["team_name"] == "Bayern Munich"
    assert fixture["teams"]["away"]["team_name"] == "VfB Stuttgart"
    assert fixture["competition"] == "Bundesliga"


def test_llm_fixture_provider_does_not_soft_accept_low_confidence_match() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {
                "match_found": False,
                "confidence": "low",
                "match_id": "STUTTGART_BAYERN_2026-05-23",
                "competition": "Bundesliga",
                "teams": {
                    "home": {"team_name": "Bayern Munich"},
                    "away": {"team_name": "VfB Stuttgart"},
                },
            }

    provider = module.LLMFixtureProvider(config=_config(), client=_Client())
    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Bayern Munich",
            away_team="Vfb Stuttgart",
            match_date="2026-05-23",
            competition="League",
        )
    )

    assert fixture is None


def test_user_prompt_json_shape_does_not_hardcode_false_for_elimination_fields() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    request = collector.MatchInputRequest(
        home_team="Bayern Munich",
        away_team="VfB Stuttgart",
        match_date="2026-05-23",
        competition="League",
    )
    prompt_json = json.loads(module.LLMFixtureProvider._build_user_prompt(request))
    shape = prompt_json["required_json_shape"]

    assert shape["is_elimination"] != False  # noqa: E712
    assert shape["overtime_possible"] != False  # noqa: E712
    assert isinstance(shape["is_elimination"], str)
    assert isinstance(shape["overtime_possible"], str)


def test_user_prompt_includes_competition_identification_rules() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    request = collector.MatchInputRequest(
        home_team="Bayern Munich",
        away_team="VfB Stuttgart",
        match_date="2026-05-23",
        competition="League",
    )
    prompt_json = json.loads(module.LLMFixtureProvider._build_user_prompt(request))
    rules = prompt_json["rules"]
    rules_text = " ".join(rules)

    assert "actual competition" in rules_text.lower() or "determine" in rules_text.lower()
    assert "cup" in rules_text.lower()
    assert "do not default to league" in rules_text.lower() or "not default to league" in rules_text.lower()


def test_system_prompt_mentions_determining_competition() -> None:
    module = load_script_module("llm_fixture_provider.py")

    system_prompt = module.LLMFixtureProvider._build_system_prompt()

    assert "competition" in system_prompt.lower()
    assert "cup" in system_prompt.lower() or "determine" in system_prompt.lower()


def test_map_fixture_includes_standings_context_from_llm_response() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {
                "match_found": True,
                "confidence": "high",
                "match_id": "BAYSTU-2026-05-23",
                "competition": "Bundesliga",
                "competition_type": "league",
                "kickoff_utc": "2026-05-23T14:30:00Z",
                "teams": {
                    "home": {
                        "team_id": "BAY",
                        "team_name": "Bayern Munich",
                        "standings_context": {
                            "table_position": 1,
                            "points": 75,
                            "games_played": 33,
                            "motivation_tag": "title_race",
                        },
                        "last_5_results": ["W", "W", "D", "W", "L"],
                    },
                    "away": {
                        "team_id": "VFB",
                        "team_name": "VfB Stuttgart",
                        "standings_context": {
                            "table_position": 5,
                            "points": 55,
                            "games_played": 33,
                            "motivation_tag": "europe_race",
                        },
                        "last_5_results": ["L", "W", "W", "D", "W"],
                    },
                },
                "venue": {"name": "Allianz Arena", "city": "Munich", "country": "Germany"},
                "status": {"long": "Not Started", "short": "NS"},
            }

    provider = module.LLMFixtureProvider(config=_config(), client=_Client())
    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Bayern Munich",
            away_team="VfB Stuttgart",
            match_date="2026-05-23",
        )
    )

    assert fixture is not None
    assert fixture["teams"]["home"]["standings_context"] == {
        "table_position": 1,
        "points": 75,
        "games_played": 33,
        "motivation_tag": "title_race",
    }
    assert fixture["teams"]["home"]["last_5_results"] == ["W", "W", "D", "W", "L"]
    assert fixture["teams"]["away"]["standings_context"] == {
        "table_position": 5,
        "points": 55,
        "games_played": 33,
        "motivation_tag": "europe_race",
    }
    assert fixture["teams"]["away"]["last_5_results"] == ["L", "W", "W", "D", "W"]


def test_map_fixture_omits_standings_when_not_in_response() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {
                "match_found": True,
                "confidence": "high",
                "match_id": "BAYSTU-2026-05-23",
                "competition": "Bundesliga",
                "competition_type": "league",
                "teams": {
                    "home": {"team_id": "BAY", "team_name": "Bayern Munich"},
                    "away": {"team_id": "VFB", "team_name": "VfB Stuttgart"},
                },
                "venue": {},
            }

    provider = module.LLMFixtureProvider(config=_config(), client=_Client())
    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Bayern Munich",
            away_team="VfB Stuttgart",
            match_date="2026-05-23",
        )
    )

    assert fixture is not None
    assert "standings_context" not in fixture["teams"]["home"]
    assert "last_5_results" not in fixture["teams"]["home"]


def test_map_fixture_handles_null_standings_fields_for_internationals() -> None:
    """National-team fixtures have no league standings; the LLM legitimately returns
    nulls for table_position/points/games_played. The mapper must coerce nulls to
    sensible defaults rather than crashing with `int(None)`."""
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {
                "match_found": True,
                "confidence": "high",
                "match_id": "GERPAR-2026-06-29",
                "competition": "International Friendly",
                "competition_type": "cup",
                "kickoff_utc": "2026-06-29T20:00:00Z",
                "teams": {
                    "home": {
                        "team_id": "GER",
                        "team_name": "Germany",
                        "standings_context": {
                            "table_position": None,
                            "points": None,
                            "games_played": None,
                            "motivation_tag": None,
                        },
                        "last_5_results": ["W", "D", "W", "L", "W"],
                    },
                    "away": {
                        "team_id": "PAR",
                        "team_name": "Paraguay",
                        "standings_context": {
                            "table_position": None,
                            "points": None,
                            "games_played": None,
                            "motivation_tag": None,
                        },
                        "last_5_results": ["L", "W", "D", "D", "W"],
                    },
                },
                "venue": {"name": "Allianz Arena", "city": "Munich", "country": "Germany"},
            }

    provider = module.LLMFixtureProvider(config=_config(), client=_Client())
    fixture = provider.lookup_fixture(
        collector.MatchInputRequest(
            home_team="Germany",
            away_team="Paraguay",
            match_date="2026-06-29",
        )
    )

    assert fixture is not None
    home_standings = fixture["teams"]["home"]["standings_context"]
    assert isinstance(home_standings["table_position"], int)
    assert isinstance(home_standings["points"], int)
    assert isinstance(home_standings["games_played"], int)
    assert isinstance(home_standings["motivation_tag"], str)
    assert home_standings["motivation_tag"]


def test_user_prompt_requests_standings_data() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")

    request = collector.MatchInputRequest(
        home_team="Bayern Munich",
        away_team="VfB Stuttgart",
        match_date="2026-05-23",
    )
    prompt_json = json.loads(module.LLMFixtureProvider._build_user_prompt(request))
    shape = prompt_json["required_json_shape"]

    home_shape = shape["teams"]["home"]
    assert "standings_context" in home_shape
    assert "last_5_results" in home_shape
    assert "table_position" in home_shape["standings_context"]
    assert "motivation_tag" in home_shape["standings_context"]


def test_fixture_provider_captures_last_sources_from_client() -> None:
    module = load_script_module("llm_fixture_provider.py")
    collector = load_script_module("collect_match_inputs.py")
    provider_config = load_script_module("provider_config.py")

    class _FakeGroundingSource:
        def __init__(self, url, title):
            self.url = url
            self.title = title

    class _ClientWithSources:
        def __init__(self):
            self.last_sources = [
                _FakeGroundingSource("https://fixture.example.com", "Fixture Source"),
            ]

        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {
                "match_found": True,
                "confidence": "high",
                "match_id": "test-123",
                "competition": "DFB Pokal",
                "competition_type": "cup",
                "kickoff_utc": "2026-05-23T18:00:00Z",
                "teams": {
                    "home": {"team_id": "BAY", "team_name": "Bayern Munich"},
                    "away": {"team_id": "VFB", "team_name": "VfB Stuttgart"},
                },
                "venue": {"name": "Olympiastadion", "city": "Berlin", "country": "Germany"},
            }

    config = provider_config.LLMFixtureProviderConfig(
        provider="gemini",
        api_key="fake-key",
        base_url="https://generativelanguage.googleapis.com/v1",
        model="gemini-2.5-flash",
    )

    provider = module.LLMFixtureProvider(config=config, client=_ClientWithSources())
    request = collector.MatchInputRequest(
        home_team="Bayern Munich",
        away_team="VfB Stuttgart",
        match_date="2026-05-23",
    )
    provider.lookup_fixture(request)

    assert len(provider.last_sources) == 1
    assert provider.last_sources[0].url == "https://fixture.example.com"
    assert provider.last_sources[0].title == "Fixture Source"
