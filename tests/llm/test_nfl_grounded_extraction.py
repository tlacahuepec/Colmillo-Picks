import json
from types import SimpleNamespace

import pytest

from llm.client import LLMError
from llm.gemini_client import GeminiLLMClient


def test_research_then_extract_retains_research_citations_and_usage():
    calls = []
    source = "https://www.nfl.com/schedules/"

    def generate(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return SimpleNamespace(
                text="The Giants host Dallas on September 13.",
                candidates=[
                    SimpleNamespace(
                        grounding_metadata=SimpleNamespace(
                            grounding_chunks=[
                                SimpleNamespace(
                                    web=SimpleNamespace(
                                        uri=source, title="NFL schedule"
                                    )
                                )
                            ],
                            grounding_supports=[
                                SimpleNamespace(
                                    segment=SimpleNamespace(
                                        start_index=0,
                                        end_index=41,
                                        text="The Giants host Dallas on September 13.",
                                    ),
                                    grounding_chunk_indices=[0],
                                )
                            ],
                            web_search_queries=["NFL schedule"],
                        )
                    )
                ],
                usage_metadata=SimpleNamespace(
                    prompt_token_count=10,
                    candidates_token_count=20,
                    total_token_count=30,
                ),
            )
        payload = json.loads(kwargs["contents"])
        assert payload["evidence"]["sources"][0]["url"] == source
        assert payload["evidence"]["supports"][0]["source_indices"] == [0]
        return SimpleNamespace(
            text='{"game": {"source_urls": ["https://www.nfl.com/schedules/"]}}',
            usage_metadata=SimpleNamespace(
                prompt_token_count=5, candidates_token_count=10, total_token_count=15
            ),
        )

    sdk = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    client = GeminiLLMClient(
        api_key="test", client_factory=lambda **kwargs: sdk, search_grounding=True
    )
    result = client.research_then_extract(
        research_prompt="Find the fixture.", schema={"type": "object"}
    )
    assert result["game"]["source_urls"] == [source]
    assert calls[0]["config"]["tools"] == [{"google_search": {}}]
    assert "tools" not in calls[1]["config"]
    assert client.last_sources[0].url == source
    assert client.cumulative_token_usage.total_tokens == 45


def test_no_source_chunks_means_no_extraction_call():
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            text="Unverified claim.",
            candidates=[SimpleNamespace(grounding_metadata=None)],
        )

    sdk = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    client = GeminiLLMClient(
        api_key="test", client_factory=lambda **kwargs: sdk, search_grounding=True
    )
    with pytest.raises(LLMError, match="source citations"):
        client.research_then_extract(research_prompt="Find fixture.", schema={})
    assert len(calls) == 1
    assert client.last_sources == []


def _grounded_research_response(source: str):
    return SimpleNamespace(
        text="The Giants host Dallas on September 13.",
        candidates=[SimpleNamespace(grounding_metadata=SimpleNamespace(
            grounding_chunks=[SimpleNamespace(web=SimpleNamespace(uri=source, title="NFL schedule"))],
            grounding_supports=[], web_search_queries=[],
        ))],
    )


def test_retries_transient_research_transport_failure_then_extracts():
    class RemoteProtocolError(Exception):
        pass

    source = "https://www.nfl.com/schedules/"
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RemoteProtocolError("connection reset")
        if len(calls) == 2:
            return _grounded_research_response(source)
        return SimpleNamespace(text='{"game": {"source_urls": ["https://www.nfl.com/schedules/"]}}')

    sdk = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    client = GeminiLLMClient(api_key="test", client_factory=lambda **_: sdk, search_grounding=True,
                             max_retries=1, sleep_fn=lambda _: None)

    assert client.research_then_extract(research_prompt="Find fixture.", schema={})["game"]["source_urls"] == [source]
    assert len(calls) == 3
    assert calls[1]["config"]["tools"] == [{"google_search": {}}]


def test_retries_extraction_without_researching_or_replacing_evidence():
    class RemoteProtocolError(Exception):
        pass

    source = "https://www.nfl.com/schedules/"
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _grounded_research_response(source)
        if len(calls) == 2:
            raise RemoteProtocolError("connection reset")
        evidence = json.loads(kwargs["contents"])["evidence"]
        assert evidence["sources"][0]["url"] == source
        return SimpleNamespace(text='{"game": {"source_urls": ["https://www.nfl.com/schedules/"]}}')

    sdk = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    client = GeminiLLMClient(api_key="test", client_factory=lambda **_: sdk, search_grounding=True,
                             max_retries=1, sleep_fn=lambda _: None)

    client.research_then_extract(research_prompt="Find fixture.", schema={})
    assert len(calls) == 3
    assert calls[0]["contents"] == "Find fixture."
    assert calls[1]["contents"] == calls[2]["contents"]


def test_does_not_retry_non_transport_provider_failure():
    calls = []

    def generate(**kwargs):
        calls.append(kwargs)
        raise ValueError("invalid API key")

    sdk = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    client = GeminiLLMClient(api_key="test", client_factory=lambda **_: sdk, search_grounding=True,
                             max_retries=2, sleep_fn=lambda _: None)

    with pytest.raises(LLMError, match="non-retryable provider failure"):
        client.research_then_extract(research_prompt="Find fixture.", schema={})
    assert len(calls) == 1
