from __future__ import annotations

import pytest

from tests.conftest import load_script_module


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


def test_llm_fixture_provider_config_infers_gemini_from_api_key() -> None:
    module = load_script_module("provider_config.py")

    values = {"GEMINI_API_KEY": "gemini-key"}
    config = module.LLMFixtureProviderConfig.from_env(values.get)

    assert config.provider == "gemini"
    assert config.api_key == "gemini-key"
