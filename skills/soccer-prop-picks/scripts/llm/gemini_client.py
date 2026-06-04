from __future__ import annotations

import json
import re
from time import sleep
from typing import Any, Callable

from llm.client import GroundingMetadataResult, GroundingSource, GroundingSupport, LLMClient, LLMError

_DEFAULT_MODEL = "gemini-2.5-flash"
_DEBUG_GROUNDING = __import__("os").environ.get("COLMILLO_DEBUG_GROUNDING", "").strip().lower() in ("1", "true", "yes")

_MARKDOWN_JSON_FENCE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def _repair_json(text: str) -> dict | None:
    """Attempt to fix common LLM JSON errors (trailing commas) and parse."""
    repaired = _TRAILING_COMMA.sub(r"\1", text)
    try:
        result = json.loads(repaired)
        return result if isinstance(result, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_json_text(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("{"):
        return stripped
    match = _MARKDOWN_JSON_FENCE.search(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _parse_first_json_object(text: str) -> dict:
    """Parse the first JSON object from text that may contain trailing data."""
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(text)
        if isinstance(obj, dict):
            return obj
        raise json.JSONDecodeError("Expected dict", text, 0)
    except json.JSONDecodeError:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            repaired = _repair_json(text)
            if repaired is not None:
                return repaired
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if match:
                extracted = match.group(0)
                try:
                    return json.loads(extracted)
                except json.JSONDecodeError:
                    repaired_extracted = _repair_json(extracted)
                    if repaired_extracted is not None:
                        return repaired_extracted
            raise


class GeminiLLMClient(LLMClient):
    """Google Gemini adapter implementing the project LLM client contract."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        max_output_tokens: int = 2000,
        timeout_seconds: float = 20.0,
        max_retries: int = 1,
        retry_delay_seconds: float = 0.5,
        search_grounding: bool = False,
        sleep_fn: Callable[[float], None] = sleep,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_delay_seconds = retry_delay_seconds
        self._search_grounding = search_grounding
        self._sleep = sleep_fn
        self._last_sources: list[GroundingSource] = []
        self._last_grounding_metadata: GroundingMetadataResult | None = None

        if client_factory is not None:
            self._client = client_factory(api_key=api_key)
        else:
            from google import genai

            self._client = genai.Client(api_key=api_key)

    @property
    def last_sources(self) -> list[GroundingSource]:
        return list(self._last_sources)

    @property
    def last_grounding_metadata(self) -> GroundingMetadataResult | None:
        return self._last_grounding_metadata

    def _extract_grounding_metadata(self, response: Any) -> GroundingMetadataResult | None:
        if not self._search_grounding:
            return None
        if not hasattr(response, "candidates") or not response.candidates:
            return None
        candidate = response.candidates[0]
        grounding_meta = getattr(candidate, "grounding_metadata", None)
        if not grounding_meta:
            return None

        sources = self._extract_sources_from_metadata(grounding_meta)
        supports = self._extract_supports_from_metadata(grounding_meta)
        web_queries = tuple(getattr(grounding_meta, "web_search_queries", None) or [])

        return GroundingMetadataResult(
            sources=tuple(sources),
            supports=supports,
            web_search_queries=web_queries,
        )

    def _extract_sources_from_metadata(self, grounding_meta: Any) -> list[GroundingSource]:
        chunks = getattr(grounding_meta, "grounding_chunks", None) or []
        sources: list[GroundingSource] = []
        for chunk in chunks:
            web = getattr(chunk, "web", None)
            if not web:
                continue
            url = getattr(web, "uri", "") or ""
            title = getattr(web, "title", "") or ""
            if url:
                sources.append(GroundingSource(url=url, title=title))
        if sources:
            return sources
        search_entry_point = getattr(grounding_meta, "search_entry_point", None)
        if search_entry_point:
            rendered = getattr(search_entry_point, "rendered_content", "") or ""
            if _DEBUG_GROUNDING:
                import sys
                print(f"[grounding-debug] search_entry_point rendered_content length: {len(rendered)}", file=sys.stderr)
                if rendered:
                    print(f"[grounding-debug] search_entry_point snippet: {rendered[:500]}", file=sys.stderr)
            if rendered:
                for match in re.finditer(r'href="(https?://[^"]+)"', rendered):
                    url = match.group(1)
                    if url not in {s.url for s in sources}:
                        sources.append(GroundingSource(url=url, title=url.split("/")[2]))
        if sources:
            return sources
        web_queries = getattr(grounding_meta, "web_search_queries", None) or []
        if _DEBUG_GROUNDING and web_queries:
            import sys
            print("[grounding-debug] Falling back to web_search_queries as source indicators", file=sys.stderr)
        return sources

    def _extract_supports_from_metadata(self, grounding_meta: Any) -> tuple[GroundingSupport, ...]:
        raw_supports = getattr(grounding_meta, "grounding_supports", None) or []
        supports: list[GroundingSupport] = []
        for support in raw_supports:
            segment = getattr(support, "segment", None)
            if not segment:
                continue
            start_index = getattr(segment, "start_index", 0) or 0
            end_index = getattr(segment, "end_index", 0) or 0
            text = getattr(segment, "text", "") or ""
            chunk_indices = tuple(getattr(support, "grounding_chunk_indices", None) or [])
            supports.append(GroundingSupport(
                start_index=start_index,
                end_index=end_index,
                text=text,
                source_indices=chunk_indices,
            ))
        return tuple(supports)

    def generate_structured(
        self, *, system_prompt: str, user_prompt: str, schema: dict, temperature: float | None = None
    ) -> dict:
        prompt = f"{system_prompt}\n\n{user_prompt}\n\nRespond with valid JSON only."
        attempts = self._max_retries + 1

        for attempt in range(1, attempts + 1):
            try:
                config: dict[str, Any] = {
                    "max_output_tokens": self._max_output_tokens,
                    "thinking_config": {"thinking_budget": 0},
                }
                if temperature is not None:
                    config["temperature"] = temperature
                if self._search_grounding:
                    config["tools"] = [{"google_search": {}}]
                else:
                    config["response_mime_type"] = "application/json"
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=config,
                )
                try:
                    text = response.text
                except (ValueError, AttributeError):
                    text = None
                if not text and hasattr(response, "candidates") and response.candidates:
                    parts = response.candidates[0].content.parts
                    if parts:
                        text = parts[0].text
                if not text or not text.strip():
                    raise LLMError("Gemini returned empty response")
                json_text = _extract_json_text(text)
                if not json_text:
                    raise LLMError("Gemini returned empty response")
                parsed = _parse_first_json_object(json_text)
                if not isinstance(parsed, dict):
                    raise LLMError("Gemini returned non-dict JSON output")
                self._last_grounding_metadata = self._extract_grounding_metadata(response)
                if self._last_grounding_metadata:
                    self._last_sources = list(self._last_grounding_metadata.sources)
                else:
                    self._last_sources = []
                return parsed
            except json.JSONDecodeError as exc:
                if attempt >= attempts:
                    raise LLMError(f"Gemini returned invalid JSON: {exc}") from exc
                self._sleep(self._retry_delay_seconds)
                continue
            except LLMError:
                if attempt >= attempts:
                    raise
                self._sleep(self._retry_delay_seconds)
                continue
            except TimeoutError as exc:
                if attempt >= attempts:
                    raise LLMError(str(exc)) from exc
                self._sleep(self._retry_delay_seconds)
            except Exception as exc:
                error_str = str(exc)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    if attempt >= attempts:
                        raise LLMError(error_str) from exc
                    retry_delay = self._retry_delay_seconds * (2 ** (attempt - 1))
                    self._sleep(min(retry_delay, 60.0))
                    continue
                raise LLMError(error_str) from exc

        raise LLMError("Gemini provider failed without returning data")
