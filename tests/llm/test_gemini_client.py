"""Tests for the Gemini LLM client and provider wiring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from llm.client import LLMError, GroundingSource, GroundingSupport
from llm.gemini_client import GeminiLLMClient
from llm.provider_adapter import build_enrich_with_llm, validate_llm_runtime_config


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeClient:
    def __init__(self, *, api_key: str):
        self.api_key = api_key
        self.models = self

    def generate_content(self, *, model, contents, config):
        return _FakeResponse('{"scores": [{"player": "A", "confidence": "high"}]}')


class _FailingClient:
    def __init__(self, *, api_key: str):
        self.models = self

    def generate_content(self, **kwargs):
        raise TimeoutError("request timed out")


def test_gemini_client_returns_parsed_json() -> None:
    client = GeminiLLMClient(api_key="test-key", client_factory=_FakeClient)

    result = client.generate_structured(
        system_prompt="You are a sports analyst.",
        user_prompt="Score these picks.",
        schema={},
    )

    assert result == {"scores": [{"player": "A", "confidence": "high"}]}


def test_gemini_client_raises_on_empty_response() -> None:
    class _EmptyClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponse("")

    client = GeminiLLMClient(api_key="test-key", client_factory=_EmptyClient)

    with pytest.raises(LLMError, match="empty response"):
        client.generate_structured(system_prompt="x", user_prompt="y", schema={})


def test_gemini_client_raises_on_whitespace_only_response() -> None:
    class _WhitespaceClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponse("\n  \n")

    client = GeminiLLMClient(api_key="test-key", client_factory=_WhitespaceClient)

    with pytest.raises(LLMError, match="empty response"):
        client.generate_structured(system_prompt="x", user_prompt="y", schema={})


def test_gemini_client_raises_on_invalid_json() -> None:
    class _BadJsonClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponse("not json at all")

    client = GeminiLLMClient(api_key="test-key", client_factory=_BadJsonClient)

    with pytest.raises(LLMError, match="invalid JSON"):
        client.generate_structured(system_prompt="x", user_prompt="y", schema={})


def test_gemini_client_retries_on_timeout() -> None:
    call_count = 0

    class _TimeoutThenSuccessClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("timed out")
            return _FakeResponse('{"ok": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_TimeoutThenSuccessClient,
        max_retries=1,
        sleep_fn=lambda _: None,
    )

    result = client.generate_structured(system_prompt="x", user_prompt="y", schema={})
    assert result == {"ok": True}
    assert call_count == 2


def test_validate_accepts_gemini_provider() -> None:
    validate_llm_runtime_config(
        use_llm=True,
        llm_provider="gemini",
        getenv=lambda k: "fake-key" if k == "GEMINI_API_KEY" else None,
    )


def test_validate_rejects_gemini_without_key() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        validate_llm_runtime_config(
            use_llm=True,
            llm_provider="gemini",
            getenv=lambda _: None,
        )


def test_build_enrich_with_llm_gemini_provider() -> None:
    enrich_fn = build_enrich_with_llm(
        use_llm=True,
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        getenv=lambda k: "fake-key" if k == "GEMINI_API_KEY" else None,
        openai_client_factory=lambda **_: MagicMock(),
    )

    assert callable(enrich_fn)


def test_validate_falls_back_to_env_var_when_no_flag() -> None:
    env = {"COLMILLO_LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "fake-key"}
    validate_llm_runtime_config(
        use_llm=True,
        llm_provider=None,
        getenv=env.get,
    )


def test_validate_error_mentions_env_var_when_neither_set() -> None:
    with pytest.raises(ValueError, match="COLMILLO_LLM_PROVIDER"):
        validate_llm_runtime_config(
            use_llm=True,
            llm_provider=None,
            getenv=lambda _: None,
        )


def test_explicit_flag_overrides_env_var() -> None:
    env = {"COLMILLO_LLM_PROVIDER": "openai", "GEMINI_API_KEY": "fake-key"}
    validate_llm_runtime_config(
        use_llm=True,
        llm_provider="gemini",
        getenv=env.get,
    )


def test_build_enrich_uses_env_provider_when_flag_is_none() -> None:
    env = {"COLMILLO_LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "fake-key"}
    enrich_fn = build_enrich_with_llm(
        use_llm=True,
        llm_provider=None,
        llm_model=None,
        getenv=env.get,
    )

    assert callable(enrich_fn)


def test_gemini_client_passes_google_search_tool_when_grounding_enabled() -> None:
    captured_config = {}

    class _CapturingClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, *, model, contents, config):
            captured_config.update(config)
            return _FakeResponse('{"match_found": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_CapturingClient,
        search_grounding=True,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert "tools" in captured_config
    assert captured_config["tools"] == [{"google_search": {}}]
    assert "response_mime_type" not in captured_config


def test_gemini_client_omits_tools_when_grounding_disabled() -> None:
    captured_config = {}

    class _CapturingClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, *, model, contents, config):
            captured_config.update(config)
            return _FakeResponse('{"match_found": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_CapturingClient,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert "tools" not in captured_config
    assert captured_config["response_mime_type"] == "application/json"


def test_gemini_client_strips_markdown_fences_from_response() -> None:
    class _MarkdownClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, *, model, contents, config):
            return _FakeResponse('```json\n{"competition": "DFB Pokal", "match_found": true}\n```')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_MarkdownClient,
        search_grounding=True,
    )
    result = client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert result == {"competition": "DFB Pokal", "match_found": True}


def test_gemini_client_parses_first_json_object_when_extra_data_follows() -> None:
    class _ExtraDataClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, *, model, contents, config):
            return _FakeResponse('{"teams": {"home": "Bayern"}}\n{"extra": "data"}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_ExtraDataClient,
        search_grounding=True,
    )
    result = client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert result == {"teams": {"home": "Bayern"}}


def test_gemini_client_retries_on_invalid_json_then_succeeds() -> None:
    call_count = 0

    class _BadThenGoodClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeResponse("not json at all")
            return _FakeResponse('{"ok": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_BadThenGoodClient,
        max_retries=1,
        sleep_fn=lambda _: None,
    )

    result = client.generate_structured(system_prompt="x", user_prompt="y", schema={})
    assert result == {"ok": True}
    assert call_count == 2


def test_gemini_client_retries_on_empty_response_then_succeeds() -> None:
    call_count = 0

    class _EmptyThenGoodClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeResponse("")
            return _FakeResponse('{"ok": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_EmptyThenGoodClient,
        max_retries=1,
        sleep_fn=lambda _: None,
    )

    result = client.generate_structured(system_prompt="x", user_prompt="y", schema={})
    assert result == {"ok": True}
    assert call_count == 2


def test_gemini_client_extracts_json_from_prose_response() -> None:
    class _ProseWrappedClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponse('Here is the fixture data:\n{"match_found": true, "teams": {}}\nSources: ...')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_ProseWrappedClient,
        search_grounding=True,
    )
    result = client.generate_structured(system_prompt="x", user_prompt="y", schema={})
    assert result == {"match_found": True, "teams": {}}


def test_gemini_client_retries_on_rate_limit_429() -> None:
    call_count = 0

    class _RateLimitClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("429 RESOURCE_EXHAUSTED: quota exceeded")
            return _FakeResponse('{"ok": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_RateLimitClient,
        max_retries=2,
        retry_delay_seconds=0.01,
        sleep_fn=lambda _: None,
    )

    result = client.generate_structured(system_prompt="x", user_prompt="y", schema={})
    assert result == {"ok": True}
    assert call_count == 2


def test_gemini_client_raises_after_exhausting_rate_limit_retries() -> None:
    class _AlwaysRateLimitClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            raise Exception("429 RESOURCE_EXHAUSTED: quota exceeded")

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_AlwaysRateLimitClient,
        max_retries=1,
        retry_delay_seconds=0.01,
        sleep_fn=lambda _: None,
    )

    with pytest.raises(LLMError, match="429"):
        client.generate_structured(system_prompt="x", user_prompt="y", schema={})


class _FakeWeb:
    def __init__(self, uri: str, title: str):
        self.uri = uri
        self.title = title


class _FakeGroundingChunk:
    def __init__(self, web: _FakeWeb):
        self.web = web


class _FakeSegment:
    def __init__(self, start_index: int, end_index: int, text: str = ""):
        self.start_index = start_index
        self.end_index = end_index
        self.text = text


class _FakeGroundingSupport:
    def __init__(self, segment: _FakeSegment, grounding_chunk_indices: list[int]):
        self.segment = segment
        self.grounding_chunk_indices = grounding_chunk_indices


class _FakeGroundingMetadata:
    def __init__(self, chunks: list[_FakeGroundingChunk], search_entry_point=None,
                 grounding_supports=None, web_search_queries=None):
        self.grounding_chunks = chunks
        self.search_entry_point = search_entry_point
        self.grounding_supports = grounding_supports
        self.web_search_queries = web_search_queries


class _FakeCandidate:
    def __init__(self, text: str, grounding_metadata=None):
        self.content = type("C", (), {"parts": [type("P", (), {"text": text})()]})()
        self.grounding_metadata = grounding_metadata


class _FakeResponseWithGrounding:
    def __init__(self, text: str, grounding_metadata=None):
        self._text = text
        self.candidates = [_FakeCandidate(text, grounding_metadata)]

    @property
    def text(self):
        return self._text


def test_gemini_client_exposes_grounding_sources() -> None:
    metadata = _FakeGroundingMetadata([
        _FakeGroundingChunk(_FakeWeb("https://example.com/page1", "Page One")),
        _FakeGroundingChunk(_FakeWeb("https://example.com/page2", "Page Two")),
    ])

    class _GroundingClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponseWithGrounding('{"match_found": true}', metadata)

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_GroundingClient,
        search_grounding=True,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert client.last_sources == [
        GroundingSource(url="https://example.com/page1", title="Page One"),
        GroundingSource(url="https://example.com/page2", title="Page Two"),
    ]


def test_gemini_client_last_sources_empty_without_grounding() -> None:
    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_FakeClient,
        search_grounding=False,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert client.last_sources == []


def test_gemini_client_last_sources_empty_when_metadata_missing() -> None:
    class _NoMetadataClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponseWithGrounding('{"ok": true}', None)

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_NoMetadataClient,
        search_grounding=True,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert client.last_sources == []


def test_gemini_client_last_sources_resets_between_calls() -> None:
    call_count = 0
    metadata = _FakeGroundingMetadata([
        _FakeGroundingChunk(_FakeWeb("https://example.com/first", "First")),
    ])

    class _ResetClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeResponseWithGrounding('{"a": 1}', metadata)
            return _FakeResponseWithGrounding('{"b": 2}', None)

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_ResetClient,
        search_grounding=True,
    )

    client.generate_structured(system_prompt="x", user_prompt="y", schema={})
    assert len(client.last_sources) == 1

    client.generate_structured(system_prompt="x", user_prompt="y", schema={})
    assert client.last_sources == []


def test_gemini_client_passes_temperature_when_provided() -> None:
    captured_config: dict = {}

    class _CapturingClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, *, model, contents, config):
            captured_config.update(config)
            return _FakeResponse('{"ok": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_CapturingClient,
    )
    client.generate_structured(
        system_prompt="x", user_prompt="y", schema={}, temperature=0.7,
    )

    assert "temperature" in captured_config
    assert captured_config["temperature"] == 0.7


def test_gemini_client_omits_temperature_when_none() -> None:
    captured_config: dict = {}

    class _CapturingClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, *, model, contents, config):
            captured_config.update(config)
            return _FakeResponse('{"ok": true}')

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_CapturingClient,
    )
    client.generate_structured(
        system_prompt="x", user_prompt="y", schema={},
    )

    assert "temperature" not in captured_config


def test_gemini_client_extracts_sources_from_search_entry_point_fallback() -> None:
    class _FakeSearchEntryPoint:
        def __init__(self):
            self.rendered_content = (
                '<a href="https://www.bbc.com/sport/football">BBC Sport</a>'
                '<a href="https://www.transfermarkt.com/bayern">Transfermarkt</a>'
            )

    metadata = _FakeGroundingMetadata(
        chunks=[],
        search_entry_point=_FakeSearchEntryPoint(),
    )

    class _EntryPointClient:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponseWithGrounding('{"match_found": true}', metadata)

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_EntryPointClient,
        search_grounding=True,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert len(client.last_sources) == 2
    assert client.last_sources[0].url == "https://www.bbc.com/sport/football"
    assert client.last_sources[1].url == "https://www.transfermarkt.com/bayern"


class TestJsonRepair:
    def test_repairs_trailing_comma_in_object(self) -> None:
        from llm.gemini_client import _repair_json

        text = '{"a": 1, "b": 2,}'
        assert _repair_json(text) == {"a": 1, "b": 2}

    def test_repairs_trailing_comma_in_array(self) -> None:
        from llm.gemini_client import _repair_json

        text = '{"items": [1, 2, 3,]}'
        assert _repair_json(text) == {"items": [1, 2, 3]}

    def test_returns_none_on_unfixable_json(self) -> None:
        from llm.gemini_client import _repair_json

        assert _repair_json("not json at all") is None

    def test_handles_nested_trailing_commas(self) -> None:
        from llm.gemini_client import _repair_json

        text = '{"a": {"b": 1,}, "c": [1,],}'
        result = _repair_json(text)
        assert result == {"a": {"b": 1}, "c": [1]}


def test_gemini_client_parses_grounding_supports() -> None:
    chunks = [
        _FakeGroundingChunk(_FakeWeb("https://example.com/a", "Source A")),
        _FakeGroundingChunk(_FakeWeb("https://example.com/b", "Source B")),
    ]
    supports = [
        _FakeGroundingSupport(
            segment=_FakeSegment(start_index=0, end_index=20, text="Bayern won 3-1"),
            grounding_chunk_indices=[0],
        ),
        _FakeGroundingSupport(
            segment=_FakeSegment(start_index=25, end_index=50, text="Lewandowski scored twice"),
            grounding_chunk_indices=[0, 1],
        ),
    ]
    metadata = _FakeGroundingMetadata(chunks=chunks, grounding_supports=supports)

    class _Client:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponseWithGrounding('{"ok": true}', metadata)

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_Client,
        search_grounding=True,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    gm = client.last_grounding_metadata
    assert gm is not None
    assert len(gm.supports) == 2
    assert gm.supports[0] == GroundingSupport(
        start_index=0, end_index=20, text="Bayern won 3-1", source_indices=(0,)
    )
    assert gm.supports[1] == GroundingSupport(
        start_index=25, end_index=50, text="Lewandowski scored twice", source_indices=(0, 1)
    )


def test_gemini_client_grounding_supports_empty_when_none() -> None:
    chunks = [_FakeGroundingChunk(_FakeWeb("https://example.com", "Ex"))]
    metadata = _FakeGroundingMetadata(chunks=chunks, grounding_supports=None)

    class _Client:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponseWithGrounding('{"ok": true}', metadata)

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_Client,
        search_grounding=True,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    gm = client.last_grounding_metadata
    assert gm is not None
    assert gm.supports == ()


def test_gemini_client_exposes_web_search_queries() -> None:
    chunks = [_FakeGroundingChunk(_FakeWeb("https://example.com", "Ex"))]
    metadata = _FakeGroundingMetadata(
        chunks=chunks,
        web_search_queries=["Bayern Munich schedule", "Bundesliga results"],
    )

    class _Client:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponseWithGrounding('{"ok": true}', metadata)

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_Client,
        search_grounding=True,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    gm = client.last_grounding_metadata
    assert gm is not None
    assert gm.web_search_queries == ("Bayern Munich schedule", "Bundesliga results")


def test_gemini_client_web_search_queries_empty_when_missing() -> None:
    chunks = [_FakeGroundingChunk(_FakeWeb("https://example.com", "Ex"))]
    metadata = _FakeGroundingMetadata(chunks=chunks, web_search_queries=None)

    class _Client:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponseWithGrounding('{"ok": true}', metadata)

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_Client,
        search_grounding=True,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    gm = client.last_grounding_metadata
    assert gm is not None
    assert gm.web_search_queries == ()


def test_gemini_client_last_grounding_metadata_none_when_disabled() -> None:
    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_FakeClient,
        search_grounding=False,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert client.last_grounding_metadata is None


def test_gemini_client_last_sources_backward_compat() -> None:
    chunks = [
        _FakeGroundingChunk(_FakeWeb("https://example.com/a", "A")),
        _FakeGroundingChunk(_FakeWeb("https://example.com/b", "B")),
    ]
    metadata = _FakeGroundingMetadata(chunks=chunks)

    class _Client:
        def __init__(self, *, api_key):
            self.models = self

        def generate_content(self, **kwargs):
            return _FakeResponseWithGrounding('{"ok": true}', metadata)

    client = GeminiLLMClient(
        api_key="test-key",
        client_factory=_Client,
        search_grounding=True,
    )
    client.generate_structured(system_prompt="x", user_prompt="y", schema={})

    assert client.last_sources == [
        GroundingSource(url="https://example.com/a", title="A"),
        GroundingSource(url="https://example.com/b", title="B"),
    ]
    gm = client.last_grounding_metadata
    assert gm is not None
    assert gm.sources == (
        GroundingSource(url="https://example.com/a", title="A"),
        GroundingSource(url="https://example.com/b", title="B"),
    )
