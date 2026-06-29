"""Tests for the LLM-powered lineup provider."""

from __future__ import annotations

from tests.conftest import load_script_module


def _fixture():
    return {
        "match_id": "BAYSTU-2026-05-23",
        "competition": "DFB Pokal",
        "competition_type": "cup",
        "kickoff_utc": "2026-05-23T18:00:00Z",
        "teams": {
            "home": {"team_id": "BAY", "team_name": "Bayern Munich"},
            "away": {"team_id": "VFB", "team_name": "VfB Stuttgart"},
        },
        "venue": {"name": "Olympiastadion", "city": "Berlin", "country": "Germany"},
    }


def _llm_response():
    return {
        "teams": {
            "home": {
                "formation": "4-2-3-1",
                "starters": [
                    "Manuel Neuer", "Joshua Kimmich", "Dayot Upamecano",
                    "Min-jae Kim", "Alphonso Davies", "Leon Goretzka",
                    "Aleksandar Pavlovic", "Serge Gnabry", "Jamal Musiala",
                    "Leroy Sane", "Harry Kane",
                ],
                "injuries": ["Kingsley Coman"],
                "suspensions": [],
            },
            "away": {
                "formation": "4-2-3-1",
                "starters": [
                    "Alexander Nubel", "Josha Vagnoman", "Jeff Chabot",
                    "Anthony Rouault", "Maximilian Mittelstadt", "Atakan Karazor",
                    "Angelo Stiller", "Chris Fuhrich", "Enzo Millot",
                    "Jamie Leweling", "Ermedin Demirovic",
                ],
                "injuries": [],
                "suspensions": ["Deniz Undav"],
            },
        },
        "players": [
            {
                "player_name": "Joshua Kimmich",
                "team": "home",
                "role_tag": "CM",
                "expected_minutes": 90,
                "substitution_risk": "low",
                "captain": True,
                "is_lone_striker": False,
                "expected_passes_per_game": 72.5,
                "expected_shots_per_game": 1.1,
            },
            {
                "player_name": "Harry Kane",
                "team": "home",
                "role_tag": "ST",
                "expected_minutes": 90,
                "substitution_risk": "low",
                "captain": False,
                "is_lone_striker": True,
                "expected_passes_per_game": 28.3,
                "expected_shots_per_game": 4.8,
            },
            {
                "player_name": "Dayot Upamecano",
                "team": "home",
                "role_tag": "CB",
                "expected_minutes": 90,
                "substitution_risk": "low",
                "captain": False,
                "is_lone_striker": False,
                "expected_passes_per_game": 62.1,
                "expected_shots_per_game": 0.3,
            },
            {
                "player_name": "Angelo Stiller",
                "team": "away",
                "role_tag": "CM",
                "expected_minutes": 88,
                "substitution_risk": "low",
                "captain": False,
                "is_lone_striker": False,
                "expected_passes_per_game": 68.4,
                "expected_shots_per_game": 0.9,
            },
            {
                "player_name": "Ermedin Demirovic",
                "team": "away",
                "role_tag": "ST",
                "expected_minutes": 85,
                "substitution_risk": "medium",
                "captain": False,
                "is_lone_striker": True,
                "expected_passes_per_game": 22.0,
                "expected_shots_per_game": 3.1,
            },
            {
                "player_name": "Jeff Chabot",
                "team": "away",
                "role_tag": "CB",
                "expected_minutes": 90,
                "substitution_risk": "low",
                "captain": True,
                "is_lone_striker": False,
                "expected_passes_per_game": 58.7,
                "expected_shots_per_game": 0.5,
            },
        ],
    }


def test_llm_lineup_provider_returns_valid_schema() -> None:
    module = load_script_module("llm_lineup_provider.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return _llm_response()

    provider = module.LLMLineupProvider(client=_Client())
    result = provider.get_lineups_and_availability(_fixture())

    assert result is not None
    assert "source_timestamp_utc" in result
    assert result["source_timestamp_utc"].endswith("Z")
    assert "teams" in result
    assert "home" in result["teams"]
    assert "away" in result["teams"]
    assert result["teams"]["home"]["formation"] == "4-2-3-1"
    assert len(result["teams"]["home"]["starters"]) == 11
    assert result["teams"]["home"]["injuries"] == ["Kingsley Coman"]
    assert result["teams"]["away"]["suspensions"] == ["Deniz Undav"]
    assert "players" in result
    assert len(result["players"]) == 6


def test_llm_lineup_provider_returns_none_on_failure() -> None:
    module = load_script_module("llm_lineup_provider.py")

    class _FailingClient:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            raise RuntimeError("LLM unavailable")

    provider = module.LLMLineupProvider(client=_FailingClient())
    result = provider.get_lineups_and_availability(_fixture())

    assert result is None


def test_llm_lineup_provider_emits_warning_on_failure(capsys) -> None:
    module = load_script_module("llm_lineup_provider.py")

    class _FailingClient:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            raise RuntimeError("LLM unavailable")

    provider = module.LLMLineupProvider(client=_FailingClient())
    provider.get_lineups_and_availability(_fixture())

    captured = capsys.readouterr()
    assert "lineup provider failed" in captured.err.lower()
    assert "LLM unavailable" in captured.err


def test_llm_lineup_provider_prompt_includes_team_names_and_date() -> None:
    module = load_script_module("llm_lineup_provider.py")
    captured_prompts = {}

    class _CapturingClient:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            captured_prompts["system"] = system_prompt
            captured_prompts["user"] = user_prompt
            return _llm_response()

    provider = module.LLMLineupProvider(client=_CapturingClient())
    provider.get_lineups_and_availability(_fixture())

    assert "Bayern Munich" in captured_prompts["user"]
    assert "VfB Stuttgart" in captured_prompts["user"]
    assert "2026-05-23" in captured_prompts["user"]


def test_llm_lineup_provider_maps_players_with_required_fields() -> None:
    module = load_script_module("llm_lineup_provider.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return _llm_response()

    provider = module.LLMLineupProvider(client=_Client())
    result = provider.get_lineups_and_availability(_fixture())

    required_fields = [
        "player_id", "player_name", "team_id", "role_tag",
        "expected_minutes", "substitution_risk", "captain",
        "is_lone_striker", "expected_passes_baseline",
        "expected_shots_baseline", "market_lines",
    ]
    for player in result["players"]:
        for field in required_fields:
            assert field in player, f"Missing field '{field}' in player {player.get('player_name')}"

    kimmich = next(p for p in result["players"] if p["player_name"] == "Joshua Kimmich")
    assert kimmich["team_id"] == "BAY"
    assert kimmich["role_tag"] == "CM"
    assert kimmich["expected_passes_baseline"] == 72.5
    assert kimmich["expected_shots_baseline"] == 1.1
    assert kimmich["captain"] is True
    assert "passes" in kimmich["market_lines"]
    assert "shots" in kimmich["market_lines"]


def _international_fixture():
    return {
        "match_id": "BRAJPN-2026-06-29",
        "competition": "International Friendly",
        "competition_type": "cup",
        "kickoff_utc": "2026-06-29T20:00:00Z",
        "teams": {
            "home": {"team_id": "BRA", "team_name": "Brazil"},
            "away": {"team_id": "JPN", "team_name": "Japan"},
        },
        "venue": {"name": "Maracana", "city": "Rio de Janeiro", "country": "Brazil"},
    }


def _international_llm_response():
    return {
        "teams": {
            "home": {
                "formation": "4-3-3",
                "starters": [
                    "Alisson", "Danilo", "Marquinhos",
                    "Gabriel Magalhaes", "Wendell", "Casemiro",
                    "Bruno Guimaraes", "Lucas Paqueta", "Vinicius Junior",
                    "Rodrygo", "Endrick",
                ],
                "injuries": ["Neymar"],
                "suspensions": [],
            },
            "away": {
                "formation": "4-2-3-1",
                "starters": [
                    "Zion Suzuki", "Hiroki Sakai", "Ko Itakura",
                    "Shogo Taniguchi", "Yukinari Sugawara", "Wataru Endo",
                    "Hidemasa Morita", "Daichi Kamada", "Takefusa Kubo",
                    "Kaoru Mitoma", "Ayase Ueda",
                ],
                "injuries": [],
                "suspensions": [],
            },
        },
        "players": [
            {
                "player_name": "Vinicius Junior",
                "team": "home",
                "role_tag": "LW",
                "expected_minutes": 85,
                "substitution_risk": "low",
                "captain": False,
                "is_lone_striker": False,
                "expected_passes_per_game": 38.4,
                "expected_shots_per_game": 4.6,
            },
            {
                "player_name": "Casemiro",
                "team": "home",
                "role_tag": "CDM",
                "expected_minutes": 90,
                "substitution_risk": "low",
                "captain": True,
                "is_lone_striker": False,
                "expected_passes_per_game": 64.2,
                "expected_shots_per_game": 0.8,
            },
            {
                "player_name": "Marquinhos",
                "team": "home",
                "role_tag": "CB",
                "expected_minutes": 90,
                "substitution_risk": "low",
                "captain": False,
                "is_lone_striker": False,
                "expected_passes_per_game": 71.0,
                "expected_shots_per_game": 0.4,
            },
            {
                "player_name": "Kaoru Mitoma",
                "team": "away",
                "role_tag": "LW",
                "expected_minutes": 85,
                "substitution_risk": "low",
                "captain": False,
                "is_lone_striker": False,
                "expected_passes_per_game": 27.6,
                "expected_shots_per_game": 2.9,
            },
            {
                "player_name": "Wataru Endo",
                "team": "away",
                "role_tag": "CDM",
                "expected_minutes": 90,
                "substitution_risk": "low",
                "captain": True,
                "is_lone_striker": False,
                "expected_passes_per_game": 55.8,
                "expected_shots_per_game": 0.6,
            },
            {
                "player_name": "Ayase Ueda",
                "team": "away",
                "role_tag": "ST",
                "expected_minutes": 80,
                "substitution_risk": "medium",
                "captain": False,
                "is_lone_striker": True,
                "expected_passes_per_game": 18.4,
                "expected_shots_per_game": 2.5,
            },
        ],
    }


def test_lineup_prompt_supports_international_fixtures() -> None:
    module = load_script_module("llm_lineup_provider.py")
    captured_prompts = {}

    class _CapturingClient:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            captured_prompts["user"] = user_prompt
            return _international_llm_response()

    provider = module.LLMLineupProvider(client=_CapturingClient())
    provider.get_lineups_and_availability(_international_fixture())

    user_prompt = captured_prompts["user"]
    assert "Brazil" in user_prompt
    assert "Japan" in user_prompt
    assert "2026-06-29" in user_prompt
    # The brittle club-only phrase must not appear; it caused the LLM to bail
    # for national-team fixtures because internationals have no "season".
    assert "current-season statistics, not estimates" not in user_prompt


def test_lineup_prompt_unchanged_essentials_for_club_fixture() -> None:
    module = load_script_module("llm_lineup_provider.py")
    captured_prompts = {}

    class _CapturingClient:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            captured_prompts["user"] = user_prompt
            return _llm_response()

    provider = module.LLMLineupProvider(client=_CapturingClient())
    provider.get_lineups_and_availability(_fixture())

    user_prompt = captured_prompts["user"]
    assert "Bayern Munich" in user_prompt
    assert "VfB Stuttgart" in user_prompt
    assert "2026-05-23" in user_prompt


def test_lineup_provider_maps_international_response() -> None:
    module = load_script_module("llm_lineup_provider.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return _international_llm_response()

    provider = module.LLMLineupProvider(client=_Client())
    result = provider.get_lineups_and_availability(_international_fixture())

    assert result is not None
    assert len(result["teams"]["home"]["starters"]) == 11
    assert len(result["teams"]["away"]["starters"]) == 11
    assert result["teams"]["home"]["injuries"] == ["Neymar"]
    assert len(result["players"]) == 6
    vinicius = next(p for p in result["players"] if p["player_name"] == "Vinicius Junior")
    assert vinicius["team_id"] == "BRA"
    assert vinicius["expected_passes_baseline"] == 38.4
    assert vinicius["expected_shots_baseline"] == 4.6


def test_lineup_provider_captures_last_sources_from_client() -> None:
    module = load_script_module("llm_lineup_provider.py")

    class _FakeGroundingSource:
        def __init__(self, url, title):
            self.url = url
            self.title = title

    class _ClientWithSources:
        def __init__(self):
            self.last_sources = [
                _FakeGroundingSource("https://lineup.example.com", "Lineup Source"),
            ]

        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return _llm_response()

    provider = module.LLMLineupProvider(client=_ClientWithSources())
    provider.get_lineups_and_availability(_fixture())

    assert len(provider.last_sources) == 1
    assert provider.last_sources[0].url == "https://lineup.example.com"
    assert provider.last_sources[0].title == "Lineup Source"
