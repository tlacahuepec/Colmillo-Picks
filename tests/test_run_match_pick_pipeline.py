from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import REPO_ROOT, load_script_module


def test_parse_match_query_with_today_keyword(
    parsed_query_fixture: str,
    resolved_match_date: str,
) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    parsed = pipeline.parse_match_query(parsed_query_fixture)

    assert parsed.home_team == "Juve"
    assert parsed.away_team == "Milan"
    assert parsed.match_date == resolved_match_date


@pytest.mark.parametrize(
    "query,expected_home,expected_away",
    [
        ("juve-milan today", "Juve", "Milan"),
        ("  juve   -   milan   today  ", "Juve", "Milan"),
        ("Juve - Milan today", "Juve", "Milan"),
    ],
)
def test_parse_match_query_supports_juve_milan_variants(query: str, expected_home: str, expected_away: str) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    parsed = pipeline.parse_match_query(query)

    assert parsed.home_team == expected_home
    assert parsed.away_team == expected_away


def test_parse_match_query_with_tomorrow_keyword() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    parsed = pipeline.parse_match_query("arsenal - liverpool tomorrow")

    assert parsed.home_team == "Arsenal"
    assert parsed.away_team == "Liverpool"
    assert parsed.match_date == (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()


def test_parse_match_query_with_iso_date() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    parsed = pipeline.parse_match_query("juve - milan 2026-05-03")

    assert parsed.home_team == "Juve"
    assert parsed.away_team == "Milan"
    assert parsed.match_date == "2026-05-03"


def test_parse_match_query_rejects_malformed_query_format() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    try:
        pipeline.parse_match_query("juve milan today")
        assert False, "Expected ValueError for malformed match query"
    except ValueError as exc:
        assert str(exc) == "Invalid match query format. Expected teams separated by '-', 'vs', or 'v'."


def test_parse_match_query_rejects_invalid_iso_date_values() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    try:
        pipeline.parse_match_query("juve - milan 2026-99-99")
        assert False, "Expected ValueError for invalid ISO date values"
    except ValueError as exc:
        assert str(exc) == "Invalid match date. Use 'today', 'tomorrow', or YYYY-MM-DD format."


def test_parse_match_query_accepts_free_form_vs_input_for_unknown_teams() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    parsed = pipeline.parse_match_query("bayern munich vs psg for tomorrow")

    assert parsed.home_team == "Bayern Munich"
    assert parsed.away_team == "Psg"
    assert parsed.match_date == (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()


def test_parse_cli_args_supports_llm_flags() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    args = pipeline.parse_cli_args(
        [
            "juve - milan today",
            "--use-llm",
            "--llm-provider",
            "openai",
            "--llm-model",
            "gpt-4.1-mini",
        ]
    )

    assert args.use_llm is True
    assert args.llm_provider == "openai"
    assert args.llm_model == "gpt-4.1-mini"


def test_parse_cli_args_supports_api_football_hints_and_fallback_flag() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    args = pipeline.parse_cli_args(
        [
            "arsenal - liverpool 2026-05-03",
            "--league",
            "Premier League",
            "--league-id",
            "39",
            "--season",
            "2025",
            "--allow-deterministic-fallback",
        ]
    )

    assert args.league == "Premier League"
    assert args.league_id == "39"
    assert args.season == "2025"
    assert args.allow_deterministic_fallback is True


def test_parse_cli_args_supports_llm_fixture_provider_flags() -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    args = pipeline.parse_cli_args(
        [
            "arsenal - liverpool 2026-05-03",
            "--fixture-provider",
            "llm",
            "--fixture-llm-provider",
            "openai-compatible",
            "--fixture-llm-model",
            "fixture-model",
            "--fixture-llm-base-url",
            "https://llm.example.test/v1",
        ]
    )

    assert args.fixture_provider == "llm"
    assert args.fixture_llm_provider == "openai-compatible"
    assert args.fixture_llm_model == "fixture-model"
    assert args.fixture_llm_base_url == "https://llm.example.test/v1"


def test_pipeline_cli_runs_end_to_end_with_single_command() -> None:
    script = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts" / "run_match_pick_pipeline.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "juve - milan today",
            "--top-n",
            "3",
            "--allow-deterministic-fallback",
        ],
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": str(os.environ.get("PATH", ""))},
    )

    report = result.stdout
    assert "Juve" in report
    assert "Milan" in report
    assert "Top 5 Recommended Picks" in report
    assert "| 1 |" in report


@pytest.mark.parametrize("invalid_top_n", ["0", "-1"])
def test_pipeline_cli_rejects_non_positive_top_n(invalid_top_n: str) -> None:
    script = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts" / "run_match_pick_pipeline.py"

    result = subprocess.run(
        [sys.executable, str(script), "juve - milan today", "--top-n", invalid_top_n],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "top-n must be a positive integer" in result.stderr


def test_pipeline_cli_rejects_llm_without_provider() -> None:
    script = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts" / "run_match_pick_pipeline.py"

    result = subprocess.run(
        [sys.executable, str(script), "juve - milan today", "--use-llm"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "--llm-provider is required when --use-llm is set" in result.stderr





def test_pipeline_cli_rejects_llm_without_credentials() -> None:
    script = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts" / "run_match_pick_pipeline.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "juve - milan today",
            "--use-llm",
            "--llm-provider",
            "openai",
            "--llm-model",
            "gpt-4.1-mini",
            "--allow-deterministic-fallback",
        ],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": str(os.environ.get("PATH", ""))},
    )

    assert result.returncode != 0
    assert "Missing credentials for provider 'openai'" in result.stderr


def test_build_dependency_bundle_includes_llm_enricher_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")
    monkeypatch.setenv("API_FOOTBALL_API_KEY", "dummy-test-key")
    monkeypatch.delenv("SOCCER_FIXTURE_PROVIDER", raising=False)

    deps = pipeline.build_dependency_bundle(use_llm=False, llm_provider=None, llm_model=None)

    assert "enrich_with_llm" in deps
    assert callable(deps["enrich_with_llm"])


def test_main_is_thin_adapter_between_cli_and_service(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    captured: dict[str, object] = {}

    def fake_parse_cli_args(argv=None):
        captured["argv"] = argv
        return type(
            "Args",
            (),
            {
                "match_query": "juve - milan today",
                "top_n": 7,
                "use_llm": True,
                "llm_provider": "openai",
                "llm_model": "gpt-4.1-mini",
                "allow_deterministic_fallback": False,
                "league": "Serie A",
                "league_id": "135",
                "season": "2025",
                "fixture_provider": "llm",
                "fixture_llm_provider": "openai-compatible",
                "fixture_llm_model": "fixture-model",
                "fixture_llm_base_url": "https://llm.example.test/v1",
            },
        )()

    deps_bundle = {"deps": "bundle"}

    def fake_build_dependency_bundle(
        *,
        use_llm,
        llm_provider,
        llm_model,
        allow_deterministic_fallback,
        league,
        league_id,
        season,
        fixture_provider_name,
        fixture_llm_provider,
        fixture_llm_model,
        fixture_llm_base_url,
    ):
        captured["build_called"] = True
        captured["bundle_args"] = {
            "use_llm": use_llm,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "allow_deterministic_fallback": allow_deterministic_fallback,
            "league": league,
            "league_id": league_id,
            "season": season,
            "fixture_provider_name": fixture_provider_name,
            "fixture_llm_provider": fixture_llm_provider,
            "fixture_llm_model": fixture_llm_model,
            "fixture_llm_base_url": fixture_llm_base_url,
        }
        return deps_bundle

    def fake_run_pipeline(*, request, deps):
        captured["request"] = request
        captured["deps"] = deps
        return "mock report"

    def fake_print(value: str):
        captured["printed"] = value

    monkeypatch.setattr(pipeline, "parse_cli_args", fake_parse_cli_args)
    monkeypatch.setattr(pipeline, "build_dependency_bundle", fake_build_dependency_bundle)
    monkeypatch.setattr(pipeline, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr("builtins.print", fake_print)

    pipeline.main()

    assert captured["build_called"] is True
    assert captured["bundle_args"] == {
        "use_llm": True,
        "llm_provider": "openai",
        "llm_model": "gpt-4.1-mini",
        "allow_deterministic_fallback": False,
        "league": "Serie A",
        "league_id": "135",
        "season": "2025",
        "fixture_provider_name": "llm",
        "fixture_llm_provider": "openai-compatible",
        "fixture_llm_model": "fixture-model",
        "fixture_llm_base_url": "https://llm.example.test/v1",
    }
    assert captured["request"] == {
        "match_query": "juve - milan today",
        "top_n": 7,
        "use_llm": True,
        "llm_provider": "openai",
        "llm_model": "gpt-4.1-mini",
        "competition": "Serie A",
    }
    assert captured["deps"] is deps_bundle
    assert captured["printed"] == "mock report"


def test_build_dependency_bundle_wires_api_providers_with_shared_config(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")
    import dependency_bundle
    monkeypatch.delenv("SOCCER_FIXTURE_PROVIDER", raising=False)

    captured: dict[str, object] = {}

    fake_config = type("_FakeConfig", (), {"api_key": "fake"})()

    class _FakeFixtureProvider:
        pass

    class _FakeOddsProvider:
        pass

    fake_config_factory = type(
        "_FakeConfigFactory", (), {"from_env": staticmethod(lambda: fake_config)}
    )
    monkeypatch.setattr(pipeline, "ApiFootballProviderConfig", fake_config_factory)
    monkeypatch.setattr(dependency_bundle, "ApiFootballProviderConfig", fake_config_factory)

    def fake_fixture_provider(*, config):
        captured["fixture_config"] = config
        return _FakeFixtureProvider()

    def fake_odds_provider(*, config):
        captured["odds_config"] = config
        return _FakeOddsProvider()

    monkeypatch.setattr(pipeline, "ApiFootballFixtureProvider", fake_fixture_provider)
    monkeypatch.setattr(pipeline, "ApiFootballOddsSnapshotProvider", fake_odds_provider)
    monkeypatch.setattr(dependency_bundle, "ApiFootballFixtureProvider", fake_fixture_provider)
    monkeypatch.setattr(dependency_bundle, "ApiFootballOddsSnapshotProvider", fake_odds_provider)

    def fake_collect_inputs(request, fixture_provider=None, odds_provider=None, allow_fixture_fallback=True, **kwargs):
        captured["fixture_provider"] = fixture_provider
        captured["odds_provider"] = odds_provider
        captured["allow_fixture_fallback"] = allow_fixture_fallback
        return {"ok": True}

    monkeypatch.setattr(pipeline, "collect_inputs", fake_collect_inputs)
    monkeypatch.setattr(dependency_bundle, "collect_inputs", fake_collect_inputs)

    deps = pipeline.build_dependency_bundle(use_llm=False, llm_provider=None, llm_model=None)
    deps["collect_inputs"](object())

    assert captured["fixture_config"] is fake_config
    assert captured["odds_config"] is fake_config
    assert captured["fixture_provider"]
    assert captured["odds_provider"]
    assert captured["allow_fixture_fallback"] is False


def test_build_dependency_bundle_requires_api_football_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    monkeypatch.delenv("API_FOOTBALL_API_KEY", raising=False)
    monkeypatch.delenv("SOCCER_FIXTURE_PROVIDER", raising=False)

    with pytest.raises(ValueError, match=r"Missing credentials for provider 'api-football'\. Set API_FOOTBALL_API_KEY\."):
        pipeline.build_dependency_bundle(use_llm=False, llm_provider=None, llm_model=None)


def test_build_dependency_bundle_wires_real_api_providers_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")
    monkeypatch.setenv("API_FOOTBALL_API_KEY", "dummy-test-key")
    monkeypatch.delenv("SOCCER_FIXTURE_PROVIDER", raising=False)

    deps = pipeline.build_dependency_bundle(use_llm=False, llm_provider=None, llm_model=None)
    closure_cells = [cell.cell_contents for cell in deps["collect_inputs"].__closure__ or ()]

    assert any(isinstance(value, pipeline.ApiFootballFixtureProvider) for value in closure_cells)
    assert any(isinstance(value, pipeline.ApiFootballOddsSnapshotProvider) for value in closure_cells)


def test_build_dependency_bundle_wires_llm_fixture_provider_without_api_football(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    captured: dict[str, object] = {}

    class _FakeLLMFixtureProvider:
        provider_label = "LLM"

        def __init__(self, *, config):
            captured["config"] = config

    import dependency_bundle
    monkeypatch.delenv("API_FOOTBALL_API_KEY", raising=False)
    monkeypatch.delenv("SOCCER_FIXTURE_PROVIDER", raising=False)
    monkeypatch.setenv("SOCCER_FIXTURE_LLM_API_KEY", "fixture-key")
    monkeypatch.setattr(pipeline, "LLMFixtureProvider", _FakeLLMFixtureProvider)
    monkeypatch.setattr(dependency_bundle, "LLMFixtureProvider", _FakeLLMFixtureProvider)

    deps = pipeline.build_dependency_bundle(
        use_llm=False,
        llm_provider=None,
        llm_model=None,
        fixture_provider_name="llm",
        fixture_llm_provider="openai-compatible",
        fixture_llm_model="fixture-model",
        fixture_llm_base_url="https://llm.example.test/v1",
    )
    closure_cells = [cell.cell_contents for cell in deps["collect_inputs"].__closure__ or ()]

    assert captured["config"].api_key == "fixture-key"
    assert captured["config"].base_url == "https://llm.example.test/v1"
    assert captured["config"].model == "fixture-model"
    assert any(isinstance(value, _FakeLLMFixtureProvider) for value in closure_cells)
    assert not any(isinstance(value, pipeline.ApiFootballFixtureProvider) for value in closure_cells)


def test_build_dependency_bundle_collect_inputs_falls_back_when_provider_payloads_are_none_or_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")
    monkeypatch.setenv("API_FOOTBALL_API_KEY", "dummy-test-key")
    monkeypatch.delenv("SOCCER_FIXTURE_PROVIDER", raising=False)

    class _FixtureProvider:
        def __init__(self, *, config):
            self.config = config

        def lookup_fixture(self, request):
            return None

    class _OddsProvider:
        def __init__(self, *, config):
            self.config = config

        def get_odds_snapshots(self, fixture):
            return {"source_timestamp_utc": "2026-05-03T10:00:00Z", "sportsbook_snapshots": [{"source": "bad-book"}]}

    import dependency_bundle
    monkeypatch.setattr(pipeline, "ApiFootballFixtureProvider", _FixtureProvider)
    monkeypatch.setattr(pipeline, "ApiFootballOddsSnapshotProvider", _OddsProvider)
    monkeypatch.setattr(dependency_bundle, "ApiFootballFixtureProvider", _FixtureProvider)
    monkeypatch.setattr(dependency_bundle, "ApiFootballOddsSnapshotProvider", _OddsProvider)

    deps = pipeline.build_dependency_bundle(
        use_llm=False,
        llm_provider=None,
        llm_model=None,
        allow_deterministic_fallback=True,
    )
    payload = deps["collect_inputs"](
        pipeline.MatchInputRequest(
            home_team="Juve",
            away_team="Milan",
            match_date="2026-05-03",
            competition="Serie A",
        )
    )

    assert payload["match"]["match_id"]
    assert len(payload["market"]["sportsbook_snapshots"]) == 2
    assert payload["validation"]["should_reject_prediction"] is True
    assert "match" in payload["validation"]["critical_missing_fields"]
    assert "market.sportsbook_snapshots" in payload["validation"]["critical_missing_fields"]


def test_build_dependency_bundle_collect_inputs_rejects_missing_fixture_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")
    monkeypatch.setenv("API_FOOTBALL_API_KEY", "dummy-test-key")
    monkeypatch.delenv("SOCCER_FIXTURE_PROVIDER", raising=False)

    class _FixtureProvider:
        def __init__(self, *, config):
            self.config = config

        def lookup_fixture(self, request):
            return None

    class _OddsProvider:
        def __init__(self, *, config):
            self.config = config

    import dependency_bundle
    monkeypatch.setattr(pipeline, "ApiFootballFixtureProvider", _FixtureProvider)
    monkeypatch.setattr(pipeline, "ApiFootballOddsSnapshotProvider", _OddsProvider)
    monkeypatch.setattr(dependency_bundle, "ApiFootballFixtureProvider", _FixtureProvider)
    monkeypatch.setattr(dependency_bundle, "ApiFootballOddsSnapshotProvider", _OddsProvider)

    deps = pipeline.build_dependency_bundle(use_llm=False, llm_provider=None, llm_model=None)

    with pytest.raises(Exception, match="Fixture lookup failed: No API-Football fixture matched Juve vs Milan on 2026-05-03\\."):
        deps["collect_inputs"](
            pipeline.MatchInputRequest(
                home_team="Juve",
                away_team="Milan",
                match_date="2026-05-03",
                competition="Serie A",
            )
        )


def test_main_reports_pipeline_service_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = load_script_module("run_match_pick_pipeline.py")

    def fake_parse_cli_args(argv=None):
        return type(
            "Args",
            (),
            {
                "match_query": "juve - milan today",
                "top_n": 5,
                "use_llm": False,
                "llm_provider": None,
                "llm_model": None,
                "allow_deterministic_fallback": False,
                "league": None,
                "league_id": None,
                "season": None,
            },
        )()

    def fake_run_pipeline(*, request, deps):
        try:
            raise ValueError("Fixture lookup failed: No API-Football fixture matched Juve vs Milan on 2026-05-03.")
        except ValueError as exc:
            raise pipeline.PipelineServiceError(stage="collect") from exc

    monkeypatch.setattr(pipeline, "parse_cli_args", fake_parse_cli_args)
    monkeypatch.setattr(pipeline, "build_dependency_bundle", lambda **kwargs: {})
    monkeypatch.setattr(pipeline, "run_pipeline", fake_run_pipeline)

    with pytest.raises(SystemExit, match="Fixture lookup failed: No API-Football fixture matched"):
        pipeline.main()
