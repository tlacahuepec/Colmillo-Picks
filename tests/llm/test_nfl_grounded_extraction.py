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
