from __future__ import annotations

import pytest

from tests.conftest import load_script_module


def test_api_football_provider_config_reads_env_values() -> None:
    module = load_script_module("provider_config.py")

    values = {
        "API_FOOTBALL_API_KEY": "  secret-key  ",
        "API_FOOTBALL_BASE_URL": " https://example.test ",
        "API_FOOTBALL_HOST": " api.example.test ",
    }

    config = module.ApiFootballProviderConfig.from_env(values.get)

    assert config.api_key == "secret-key"
    assert config.base_url == "https://example.test"
    assert config.host == "api.example.test"


def test_api_football_provider_config_validate_requires_api_key() -> None:
    module = load_script_module("provider_config.py")
    config = module.ApiFootballProviderConfig(api_key=None, base_url="https://x.test", host="v3.football.api-sports.io")

    with pytest.raises(ValueError, match="Missing credentials for provider 'api-football'\\. Set API_FOOTBALL_API_KEY\\."):
        config.validate()
