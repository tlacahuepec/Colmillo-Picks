from __future__ import annotations

import os
from typing import Callable

from llm.langchain_enricher import LangChainEnricher, default_prompt_builder, default_structured_parser
from llm.langgraph_flow import SimpleLangGraphFlow
from llm.mock_client import DeterministicMockLLMClient
from llm.openai_client import OpenAILLMClient
from llm.gemini_client import GeminiLLMClient
from llm.grok_client import GrokLLMClient

_DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
_DEFAULT_GROK_MODEL = "grok-3"
_DEFAULT_XAI_BASE_URL = "https://api.x.ai/v1"


def _read_langgraph_toggle(getenv: Callable[[str], str | None]) -> bool:
    value = getenv("COLMILLO_USE_LANGGRAPH") or ""
    return value.strip().lower() in ("true", "1")


def _as_chat_model(client: object) -> Callable[[dict[str, str]], dict]:
    def chat_model(prompt: dict[str, str]) -> dict:
        return client.generate_structured(system_prompt=prompt["system"], user_prompt=prompt["user"], schema={})

    return chat_model


def _resolve_llm_provider(llm_provider: str | None, getenv: Callable[[str], str | None]) -> str | None:
    if llm_provider:
        return llm_provider
    return getenv("COLMILLO_LLM_PROVIDER")


def validate_llm_runtime_config(*, use_llm: bool, llm_provider: str | None, getenv: Callable[[str], str | None] = os.getenv) -> None:
    if not use_llm:
        return

    resolved = _resolve_llm_provider(llm_provider, getenv)
    if not resolved:
        raise ValueError(
            "--llm-provider is required when --use-llm is set. "
            "Pass it as a flag or set COLMILLO_LLM_PROVIDER in your environment."
        )

    provider = resolved.lower().strip()
    if provider not in {"openai", "gemini", "grok"}:
        raise ValueError(f"Unsupported --llm-provider '{resolved}'. Supported values: openai, gemini, grok.")

    if provider == "openai" and not getenv("OPENAI_API_KEY"):
        raise ValueError("Missing credentials for provider 'openai'. Set OPENAI_API_KEY.")
    if provider == "gemini" and not getenv("GEMINI_API_KEY"):
        raise ValueError("Missing credentials for provider 'gemini'. Set GEMINI_API_KEY.")
    if provider == "grok" and not getenv("XAI_API_KEY"):
        raise ValueError("Missing credentials for provider 'grok'. Set XAI_API_KEY.")


def build_enrich_with_llm(
    *,
    use_llm: bool,
    llm_provider: str | None,
    llm_model: str | None,
    use_langgraph: bool = False,
    getenv: Callable[[str], str | None] = os.getenv,
    openai_client_factory: Callable[..., object] | None = None,
):
    if not use_llm:
        client = DeterministicMockLLMClient()
    else:
        resolved_provider = _resolve_llm_provider(llm_provider, getenv)
        validate_llm_runtime_config(use_llm=use_llm, llm_provider=resolved_provider, getenv=getenv)
        provider = str(resolved_provider).lower().strip()
        if provider == "gemini":
            client = GeminiLLMClient(
                api_key=getenv("GEMINI_API_KEY"),
                model=(llm_model or _DEFAULT_GEMINI_MODEL),
            )
        elif provider == "openai":
            if openai_client_factory is None:
                from openai import OpenAI

                openai_client_factory = OpenAI

            sdk_client = openai_client_factory(api_key=getenv("OPENAI_API_KEY"))
            client = OpenAILLMClient(sdk_client=sdk_client, model=(llm_model or _DEFAULT_OPENAI_MODEL))
        elif provider == "grok":
            client = GrokLLMClient(
                api_key=getenv("XAI_API_KEY") or "",
                base_url=getenv("XAI_BASE_URL") or _DEFAULT_XAI_BASE_URL,
                model=(llm_model or getenv("XAI_MODEL") or _DEFAULT_GROK_MODEL),
            )
        else:
            raise ValueError(f"Unsupported --llm-provider '{resolved_provider}'. Supported values: openai, gemini.")

    chat_model = _as_chat_model(client)

    if use_langgraph:
        flow = SimpleLangGraphFlow(
            prompt_builder=default_prompt_builder,
            chat_model=chat_model,
            structured_parser=default_structured_parser,
        )

        def enrich_with_llm(*, scored_payload: dict, match_inputs: dict) -> dict:
            return flow.run(scored_payload=scored_payload, match_inputs=match_inputs, top_n=5)["result"]

        return enrich_with_llm

    enricher = LangChainEnricher(
        prompt_builder=default_prompt_builder,
        chat_model=chat_model,
        structured_parser=default_structured_parser,
    )

    def enrich_with_llm(*, scored_payload: dict, match_inputs: dict) -> dict:
        return enricher.enrich(scored_payload=scored_payload, match_inputs=match_inputs, top_n=5)

    return enrich_with_llm
