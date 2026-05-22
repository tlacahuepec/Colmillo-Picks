"""Tests for the run_daily_intelligence CLI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import load_script_module


def _load():
    return load_script_module("run_daily_intelligence.py")


def _minimal_briefing() -> dict:
    return {
        "schema_version": "v1.0.0",
        "date_utc": "2026-05-21",
        "generated_at_utc": "2026-05-21T10:00:00Z",
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "top_matches": [],
    }


def test_parse_cli_args_default_top_n_is_five() -> None:
    module = _load()
    args = module.parse_cli_args([])
    assert args.top_n == 5


def test_parse_cli_args_default_date_is_today_utc() -> None:
    module = _load()
    args = module.parse_cli_args([])
    assert args.date == datetime.now(timezone.utc).date().isoformat()


def test_parse_cli_args_accepts_explicit_date() -> None:
    module = _load()
    args = module.parse_cli_args(["--date", "2026-05-21"])
    assert args.date == "2026-05-21"


def test_parse_cli_args_accepts_top_n() -> None:
    module = _load()
    args = module.parse_cli_args(["--top-n", "3"])
    assert args.top_n == 3


def test_parse_cli_args_rejects_top_n_above_max() -> None:
    module = _load()
    with pytest.raises(SystemExit):
        module.parse_cli_args(["--top-n", "11"])


def test_parse_cli_args_rejects_top_n_below_min() -> None:
    module = _load()
    with pytest.raises(SystemExit):
        module.parse_cli_args(["--top-n", "0"])


def test_parse_cli_args_rejects_invalid_date_format() -> None:
    module = _load()
    with pytest.raises(SystemExit):
        module.parse_cli_args(["--date", "not-a-date"])


def test_parse_cli_args_accepts_provider_flag() -> None:
    module = _load()
    args = module.parse_cli_args(["--provider", "grok"])
    assert args.provider == "grok"


def test_parse_cli_args_provider_defaults_to_none() -> None:
    module = _load()
    args = module.parse_cli_args([])
    assert args.provider is None


def test_main_prints_json_to_stdout_on_success(capsys) -> None:
    module = _load()
    briefing = _minimal_briefing()

    mock_client = MagicMock()
    mock_client.fetch_daily_briefing.return_value = briefing

    with patch.object(module, "DailyIntelligenceClient") as MockClass:
        MockClass.from_env.return_value = mock_client
        module.main(["--date", "2026-05-21", "--top-n", "1"])

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["schema_version"] == "v1.0.0"


def test_main_writes_json_to_file(tmp_path) -> None:
    module = _load()
    briefing = _minimal_briefing()
    output_file = tmp_path / "briefing.json"

    mock_client = MagicMock()
    mock_client.fetch_daily_briefing.return_value = briefing

    with patch.object(module, "DailyIntelligenceClient") as MockClass:
        MockClass.from_env.return_value = mock_client
        module.main(["--date", "2026-05-21", "--output-json", str(output_file)])

    assert output_file.exists()
    parsed = json.loads(output_file.read_text())
    assert parsed["schema_version"] == "v1.0.0"


def test_main_exits_with_error_when_api_key_missing() -> None:
    module = _load()

    with patch.object(module, "DailyIntelligenceClient") as MockClass:
        MockClass.from_env.side_effect = module.DailyIntelligenceError("GEMINI_API_KEY is required")
        with pytest.raises(SystemExit, match="Error:"):
            module.main(["--date", "2026-05-21"])


def test_main_exits_with_error_on_fetch_failure() -> None:
    module = _load()
    mock_client = MagicMock()
    mock_client.fetch_daily_briefing.side_effect = module.DailyIntelligenceError("provider timeout")

    with patch.object(module, "DailyIntelligenceClient") as MockClass:
        MockClass.from_env.return_value = mock_client
        with pytest.raises(SystemExit, match="Error:"):
            module.main(["--date", "2026-05-21"])


def test_main_passes_provider_to_from_env() -> None:
    module = _load()
    briefing = _minimal_briefing()

    mock_client = MagicMock()
    mock_client.fetch_daily_briefing.return_value = briefing

    with patch.object(module, "DailyIntelligenceClient") as MockClass:
        MockClass.from_env.return_value = mock_client
        module.main(["--provider", "grok", "--date", "2026-05-21"])

    MockClass.from_env.assert_called_once_with(provider="grok")
