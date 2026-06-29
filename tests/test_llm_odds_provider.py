"""Tests for the LLM-powered odds provider."""

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
        "sportsbook_snapshots": [
            {"source": "bet365", "odds_decimal": 1.45},
            {"source": "DraftKings", "odds_decimal": 1.47},
            {"source": "FanDuel", "odds_decimal": 1.44},
            {"source": "BetMGM", "odds_decimal": 1.46},
            {"source": "Pinnacle", "odds_decimal": 1.48},
            {"source": "Unibet", "odds_decimal": 1.45},
        ],
    }


def test_llm_odds_provider_returns_valid_schema() -> None:
    module = load_script_module("llm_odds_provider.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return _llm_response()

    provider = module.LLMOddsProvider(client=_Client())
    result = provider.get_odds_snapshots(_fixture())

    assert result is not None
    assert "source_timestamp_utc" in result
    assert result["source_timestamp_utc"].endswith("Z")
    assert "sportsbook_snapshots" in result
    assert len(result["sportsbook_snapshots"]) == 6


def test_llm_odds_provider_snapshots_have_required_fields() -> None:
    module = load_script_module("llm_odds_provider.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return _llm_response()

    provider = module.LLMOddsProvider(client=_Client())
    result = provider.get_odds_snapshots(_fixture())

    for snap in result["sportsbook_snapshots"]:
        assert "source" in snap
        assert "odds_decimal" in snap
        assert "captured_at_utc" in snap
        assert isinstance(snap["odds_decimal"], float)
        assert snap["odds_decimal"] > 1.0

    bet365 = next(s for s in result["sportsbook_snapshots"] if s["source"] == "bet365")
    assert bet365["odds_decimal"] == 1.45


def test_llm_odds_provider_returns_none_on_failure() -> None:
    module = load_script_module("llm_odds_provider.py")

    class _FailingClient:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            raise RuntimeError("LLM unavailable")

    provider = module.LLMOddsProvider(client=_FailingClient())
    result = provider.get_odds_snapshots(_fixture())

    assert result is None


def test_llm_odds_provider_returns_none_for_empty_snapshots() -> None:
    module = load_script_module("llm_odds_provider.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {"sportsbook_snapshots": []}

    provider = module.LLMOddsProvider(client=_Client())
    result = provider.get_odds_snapshots(_fixture())

    assert result is None


def test_llm_odds_provider_filters_invalid_odds() -> None:
    module = load_script_module("llm_odds_provider.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {
                "sportsbook_snapshots": [
                    {"source": "bet365", "odds_decimal": 1.45},
                    {"source": "bad_book", "odds_decimal": 0.5},
                    {"source": "null_book", "odds_decimal": None},
                    {"source": "Pinnacle", "odds_decimal": 1.48},
                ],
            }

    provider = module.LLMOddsProvider(client=_Client())
    result = provider.get_odds_snapshots(_fixture())

    assert result is not None
    assert len(result["sportsbook_snapshots"]) == 2
    sources = [s["source"] for s in result["sportsbook_snapshots"]]
    assert "bet365" in sources
    assert "Pinnacle" in sources


def test_llm_odds_provider_prompt_includes_team_names_and_date() -> None:
    module = load_script_module("llm_odds_provider.py")
    captured_prompts = {}

    class _CapturingClient:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            captured_prompts["system"] = system_prompt
            captured_prompts["user"] = user_prompt
            return _llm_response()

    provider = module.LLMOddsProvider(client=_CapturingClient())
    provider.get_odds_snapshots(_fixture())

    assert "Bayern Munich" in captured_prompts["user"]
    assert "VfB Stuttgart" in captured_prompts["user"]
    assert "2026-05-23" in captured_prompts["user"]


def test_llm_odds_provider_emits_warning_on_failure(capsys) -> None:
    module = load_script_module("llm_odds_provider.py")

    class _FailingClient:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            raise RuntimeError("LLM unavailable")

    provider = module.LLMOddsProvider(client=_FailingClient())
    provider.get_odds_snapshots(_fixture())

    captured = capsys.readouterr()
    assert "odds provider failed" in captured.err.lower()
    assert "LLM unavailable" in captured.err


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


def test_odds_prompt_supports_international_fixtures() -> None:
    module = load_script_module("llm_odds_provider.py")
    captured_prompts = {}

    class _CapturingClient:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            captured_prompts["user"] = user_prompt
            return _llm_response()

    provider = module.LLMOddsProvider(client=_CapturingClient())
    provider.get_odds_snapshots(_international_fixture())

    user_prompt = captured_prompts["user"]
    assert "Brazil" in user_prompt
    assert "Japan" in user_prompt
    assert "2026-06-29" in user_prompt
    # The escape clause caused the LLM to return empty for any fixture where
    # indexed sportsbook pages are sparse (typical for internationals).
    assert "If odds are not yet available" not in user_prompt
    # The strict 5-sportsbook minimum forced the LLM into the escape clause.
    assert "at least 5 sportsbooks" not in user_prompt


def test_odds_prompt_unchanged_essentials_for_club_fixture() -> None:
    module = load_script_module("llm_odds_provider.py")
    captured_prompts = {}

    class _CapturingClient:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            captured_prompts["user"] = user_prompt
            return _llm_response()

    provider = module.LLMOddsProvider(client=_CapturingClient())
    provider.get_odds_snapshots(_fixture())

    user_prompt = captured_prompts["user"]
    assert "Bayern Munich" in user_prompt
    assert "VfB Stuttgart" in user_prompt
    assert "2026-05-23" in user_prompt


def test_odds_provider_accepts_single_sportsbook_for_international() -> None:
    module = load_script_module("llm_odds_provider.py")

    class _Client:
        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return {"sportsbook_snapshots": [{"source": "bet365", "odds_decimal": 1.62}]}

    provider = module.LLMOddsProvider(client=_Client())
    result = provider.get_odds_snapshots(_international_fixture())

    assert result is not None
    assert len(result["sportsbook_snapshots"]) == 1
    assert result["sportsbook_snapshots"][0]["source"] == "bet365"
    assert result["sportsbook_snapshots"][0]["odds_decimal"] == 1.62


def test_odds_provider_captures_last_sources_from_client() -> None:
    module = load_script_module("llm_odds_provider.py")

    class _FakeGroundingSource:
        def __init__(self, url, title):
            self.url = url
            self.title = title

    class _ClientWithSources:
        def __init__(self):
            self.last_sources = [
                _FakeGroundingSource("https://odds.example.com", "Odds Source"),
            ]

        def generate_structured(self, *, system_prompt, user_prompt, schema):
            return _llm_response()

    provider = module.LLMOddsProvider(client=_ClientWithSources())
    provider.get_odds_snapshots(_fixture())

    assert len(provider.last_sources) == 1
    assert provider.last_sources[0].url == "https://odds.example.com"
    assert provider.last_sources[0].title == "Odds Source"
