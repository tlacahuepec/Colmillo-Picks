from __future__ import annotations

import os
from typing import Callable

from llm.langchain_enricher import LangChainEnricher, default_prompt_builder, default_structured_parser
from llm.langgraph_flow import SimpleLangGraphFlow
from llm.mock_client import DeterministicMockLLMClient
from llm.openai_client import OpenAILLMClient

_DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


def _as_chat_model(client: object) -> Callable[[dict[str, str]], dict]:
    def chat_model(prompt: dict[str, str]) -> dict:
        return client.generate_structured(system_prompt=prompt["system"], user_prompt=prompt["user"], schema={})

    return chat_model


def validate_llm_runtime_config(*, use_llm: bool, llm_provider: str | None, getenv: Callable[[str], str | None] = os.getenv) -> None:
    if not use_llm:
        return

    if not llm_provider:
        raise ValueError("--llm-provider is required when --use-llm is set.")

    provider = llm_provider.lower().strip()
    if provider != "openai":
        raise ValueError(f"Unsupported --llm-provider '{llm_provider}'. Supported values: openai.")

    if not getenv("OPENAI_API_KEY"):
        raise ValueError("Missing credentials for provider 'openai'. Set OPENAI_API_KEY.")


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
        validate_llm_runtime_config(use_llm=use_llm, llm_provider=llm_provider, getenv=getenv)
        provider = str(llm_provider).lower().strip()
        if provider != "openai":
            raise ValueError(f"Unsupported --llm-provider '{llm_provider}'. Supported values: openai.")

        if openai_client_factory is None:
            from openai import OpenAI

            openai_client_factory = OpenAI

        sdk_client = openai_client_factory(api_key=getenv("OPENAI_API_KEY"))
        client = OpenAILLMClient(sdk_client=sdk_client, model=(llm_model or _DEFAULT_OPENAI_MODEL))

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
