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


def test_llm_fixture_provider_config_reads_openai_env_values() -> None:
    module = load_script_module("provider_config.py")

    values = {
        "OPENAI_API_KEY": " openai-key ",
        "OPENAI_BASE_URL": " https://openai.example.test/v1 ",
        "OPENAI_MODEL": " gpt-test ",
    }

    config = module.LLMFixtureProviderConfig.from_env(values.get)

    assert config.provider == "openai"
    assert config.api_key == "openai-key"
    assert config.base_url == "https://openai.example.test/v1"
    assert config.model == "gpt-test"


def test_llm_fixture_provider_config_reads_grok_alias() -> None:
    module = load_script_module("provider_config.py")

    values = {
        "SOCCER_FIXTURE_LLM_PROVIDER": " grok ",
        "GROK_API_KEY": " grok-key ",
        "GROK_BASE_URL": " https://grok.example.test/v1 ",
        "GROK_MODEL": " grok-test ",
    }

    config = module.LLMFixtureProviderConfig.from_env(values.get)

    assert config.provider == "xai"
    assert config.api_key == "grok-key"
    assert config.base_url == "https://grok.example.test/v1"
    assert config.model == "grok-test"


def test_llm_fixture_provider_config_validate_requires_generic_model() -> None:
    module = load_script_module("provider_config.py")
    config = module.LLMFixtureProviderConfig(
        provider="openai-compatible",
        api_key="fixture-key",
        base_url="https://llm.example.test/v1",
        model=None,
    )

    with pytest.raises(ValueError, match="SOCCER_FIXTURE_LLM_MODEL"):
        config.validate()
