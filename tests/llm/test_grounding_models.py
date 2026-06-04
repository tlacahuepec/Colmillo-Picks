"""Tests for grounding data models."""

from __future__ import annotations

import pytest

from llm.client import GroundingSource, GroundingSupport, GroundingMetadataResult


class TestGroundingSupport:
    def test_construction(self) -> None:
        support = GroundingSupport(
            start_index=0,
            end_index=42,
            text="Bayern Munich won 3-1",
            source_indices=(0, 1),
        )
        assert support.start_index == 0
        assert support.end_index == 42
        assert support.text == "Bayern Munich won 3-1"
        assert support.source_indices == (0, 1)

    def test_frozen_immutability(self) -> None:
        support = GroundingSupport(
            start_index=0,
            end_index=10,
            text="test",
            source_indices=(0,),
        )
        with pytest.raises(AttributeError):
            support.start_index = 5  # type: ignore[misc]

    def test_equality(self) -> None:
        a = GroundingSupport(start_index=0, end_index=10, text="x", source_indices=(0,))
        b = GroundingSupport(start_index=0, end_index=10, text="x", source_indices=(0,))
        assert a == b

    def test_empty_source_indices(self) -> None:
        support = GroundingSupport(
            start_index=0,
            end_index=5,
            text="hello",
            source_indices=(),
        )
        assert support.source_indices == ()


class TestGroundingMetadataResult:
    def test_construction_with_data(self) -> None:
        sources = (
            GroundingSource(url="https://example.com", title="Example"),
        )
        supports = (
            GroundingSupport(start_index=0, end_index=10, text="test", source_indices=(0,)),
        )
        queries = ("Bayern Munich schedule",)

        result = GroundingMetadataResult(
            sources=sources,
            supports=supports,
            web_search_queries=queries,
        )

        assert result.sources == sources
        assert result.supports == supports
        assert result.web_search_queries == queries

    def test_construction_empty(self) -> None:
        result = GroundingMetadataResult(
            sources=(),
            supports=(),
            web_search_queries=(),
        )
        assert result.sources == ()
        assert result.supports == ()
        assert result.web_search_queries == ()

    def test_frozen_immutability(self) -> None:
        result = GroundingMetadataResult(
            sources=(),
            supports=(),
            web_search_queries=(),
        )
        with pytest.raises(AttributeError):
            result.sources = ()  # type: ignore[misc]


class TestGroundingSourceRegression:
    def test_existing_source_unchanged(self) -> None:
        source = GroundingSource(url="https://bbc.com", title="BBC")
        assert source.url == "https://bbc.com"
        assert source.title == "BBC"

    def test_frozen(self) -> None:
        source = GroundingSource(url="https://x.com", title="X")
        with pytest.raises(AttributeError):
            source.url = "other"  # type: ignore[misc]
