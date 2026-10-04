from __future__ import annotations

from diagnostics_support import diagnostic_stage, emit, provider_attempt, retry_sleep

import json
import re
from time import sleep
from typing import Any, Callable

from llm.client import GroundingMetadataResult, GroundingSource, GroundingSupport, LLMClient, LLMError, TokenUsage

_DEFAULT_MODEL = "gemini-2.5-flash"
_DEBUG_GROUNDING = __import__("os").environ.get("COLMILLO_DEBUG_GROUNDING", "").strip().lower() in ("1", "true", "yes")

_MARKDOWN_JSON_FENCE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_CITATION_ANNOTATION = re.compile(r"\s*\[cite:\s*[\d,\s]+\]")
_BARE_CITATION = re.compile(r'"\s*\[\d+(?:,\s*\d+)*\]')
_RETRYABLE_TRANSPORT_MARKERS = (
    "remoteprotocolerror", "connecttimeout", "readtimeout", "timeout", "timed out",
    "connection reset", "connection aborted", "service unavailable", "bad gateway",
    "internal server error", "http 429", "http 500", "http 502", "http 503", "http 504",
)


def _is_retryable_transport_error(exc: Exception) -> bool:
    """Keep retries for transient transport/provider failures, never auth or schema errors."""
    if isinstance(exc, TimeoutError):
        return True
    detail = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in detail for marker in _RETRYABLE_TRANSPORT_MARKERS)


def _sdk_http_options(timeout_seconds: float) -> dict[str, int]:
    """Convert the public seconds setting to google-genai's milliseconds."""
    return {"timeout": max(1, round(timeout_seconds * 1000))}


def _strip_citations(text: str) -> str:
    """Remove both [cite: N, N] and bare [N, N] citation markers from text."""
    result = _CITATION_ANNOTATION.sub("", text)
    result = _BARE_CITATION.sub('"', result)
    return result


def _repair_json(text: str) -> dict | None:
    """Attempt to fix common LLM JSON errors (trailing commas, bracket mismatches, unclosed strings/brackets, glued objects) and parse."""
    cleaned = _MARKDOWN_JSON_FENCE.sub(r"\1", text).strip()

    # Split glued JSON objects (e.g. '}{' or '}\n{') if multiple objects exist
    chunks = re.split(r"(?<=\})\s*(?=\{)", cleaned)
    for chunk in chunks:
        fast_repaired = _TRAILING_COMMA.sub(r"\1", chunk).strip()
        try:
            result = json.loads(fast_repaired)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        out: list[str] = []
        in_string = False
        escape = False
        stack: list[str] = []

        for ch in chunk:
            if escape:
                out.append(ch)
                escape = False
                continue
            if ch == "\\" and in_string:
                out.append(ch)
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                out.append(ch)
                continue
            if in_string:
                out.append(ch)
                continue

            if ch in ("{", "["):
                stack.append(ch)
                out.append(ch)
            elif ch in ("}", "]"):
                if not stack:
                    continue  # Ignore orphaned closer
                expected = "}" if stack[-1] == "{" else "]"
                if ch != expected:
                    out.append(expected)
                    stack.pop()
                else:
                    out.append(ch)
                    stack.pop()
            else:
                out.append(ch)

        if in_string:
            out.append('"')

        repaired = "".join(out)
        repaired = re.sub(r",\s*$", "", repaired)
        repaired = _TRAILING_COMMA.sub(r"\1", repaired)

        for opener in reversed(stack):
            repaired += "}" if opener == "{" else "]"
        repaired = _TRAILING_COMMA.sub(r"\1", repaired)

        try:
            result = json.loads(repaired)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        last_bracket = max(repaired.rfind("}"), repaired.rfind("]"))
        while last_bracket > 0:
            candidate = repaired[:last_bracket + 1]
            c_stack: list[str] = []
            c_in_str = False
            c_esc = False
            for c in candidate:
                if c_esc:
                    c_esc = False
                    continue
                if c == "\\" and c_in_str:
                    c_esc = True
                    continue
                if c == '"':
                    c_in_str = not c_in_str
                    continue
                if c_in_str:
                    continue
                if c in ("{", "["):
                    c_stack.append(c)
                elif c in ("}", "]") and c_stack:
                    c_stack.pop()
            candidate_repaired = _TRAILING_COMMA.sub(r"\1", candidate)
            for op in reversed(c_stack):
                candidate_repaired += "}" if op == "{" else "]"
            candidate_repaired = _TRAILING_COMMA.sub(r"\1", candidate_repaired)
            try:
                result = json.loads(candidate_repaired)
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, ValueError):
                pass
            last_bracket = max(repaired.rfind("}", 0, last_bracket), repaired.rfind("]", 0, last_bracket))

    return None


def _extract_json_text(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("{"):
        return stripped
    match = _MARKDOWN_JSON_FENCE.search(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _best_json_part(parts: list) -> str | None:
    """Try each part to find one containing parseable JSON."""
    for part in parts:
        text = getattr(part, "text", None)
        if not text or not text.strip():
            continue
        extracted = _extract_json_text(text)
        if not extracted:
            continue
        try:
            _parse_first_json_object(extracted)
            return text
        except (json.JSONDecodeError, ValueError, LLMError):
            continue
    return getattr(parts[0], "text", None) if parts else None


def _parse_first_json_object(text: str) -> dict:
    """Parse the first JSON object from text that may contain trailing data."""
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(text)
        if isinstance(obj, dict):
            return obj
        raise json.JSONDecodeError("Expected dict", text, 0)
    except json.JSONDecodeError:
        pass

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    cleaned = _strip_citations(text)
    try:
        obj, _ = decoder.raw_decode(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    repaired = _repair_json(cleaned)
    if repaired is not None:
        return repaired

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        extracted = match.group(0)
        try:
            obj = json.loads(extracted)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            repaired_extracted = _repair_json(extracted)
            if repaired_extracted is not None:
                return repaired_extracted

    raise json.JSONDecodeError("No valid JSON object found", text, 0)


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
        self._sleep = retry_sleep(sleep_fn, provider="gemini", model=model)
        self._last_sources: list[GroundingSource] = []
        self._last_grounding_metadata: GroundingMetadataResult | None = None
        self._last_token_usage: TokenUsage | None = None
        self._cumulative_tokens: list[int] = [0, 0, 0]

        if client_factory is not None:
            self._client = client_factory(api_key=api_key)
        else:
            from google import genai

            self._client = genai.Client(
                api_key=api_key,
                http_options=_sdk_http_options(timeout_seconds),
            )

    @property
    def last_sources(self) -> list[GroundingSource]:
        return list(self._last_sources)

    @property
    def last_grounding_metadata(self) -> GroundingMetadataResult | None:
        return self._last_grounding_metadata

    @property
    def last_token_usage(self) -> TokenUsage | None:
        return self._last_token_usage

    @property
    def cumulative_token_usage(self) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self._cumulative_tokens[0],
            completion_tokens=self._cumulative_tokens[1],
            total_tokens=self._cumulative_tokens[2],
        )

    def reset_cumulative_tokens(self) -> None:
        self._cumulative_tokens = [0, 0, 0]

    def _record_research_usage(self, response: Any) -> None:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            self._last_token_usage = None
            return
        counts = [getattr(usage, key, 0) or 0 for key in
                  ("prompt_token_count", "candidates_token_count", "total_token_count")]
        self._last_token_usage = TokenUsage(*counts)
        self._cumulative_tokens = [old + new for old, new in zip(self._cumulative_tokens, counts)]
        emit("provider.usage", provider="gemini", model=self._model,
             prompt_tokens=counts[0], completion_tokens=counts[1], total_tokens=counts[2])

    @diagnostic_stage("llm_research_extract", provider="gemini")
    def research_then_extract(self, *, research_prompt: str, schema: dict) -> dict:
        """Research with citations first, then extract JSON without another search.

        The extraction response never replaces the original grounding metadata.
        Used by NFL collection; existing structured-generation behavior is unchanged.
        """
        from dataclasses import asdict

        def request_with_retry(stage: str, *, contents: str, config: dict[str, Any]) -> Any:
            attempts = self._max_retries + 1
            for attempt in range(1, attempts + 1):
                try:
                    with provider_attempt("gemini", model=self._model, stage=stage, attempt=attempt):
                        return self._client.models.generate_content(
                            model=self._model, contents=contents, config=config,
                        )
                except Exception as exc:
                    retryable = _is_retryable_transport_error(exc)
                    if retryable and attempt < attempts:
                        emit("provider.retry", provider="gemini", model=self._model, stage=stage,
                             attempt=attempt, error_type=type(exc).__name__)
                        self._sleep(self._retry_delay_seconds)
                        continue
                    disposition = "retryable transport failure exhausted" if retryable else "non-retryable provider failure"
                    raise LLMError(f"{stage} {disposition} after {attempt} attempt(s): {type(exc).__name__}.") from exc

        self._last_sources = []
        self._last_grounding_metadata = None
        self.last_research_evidence = None
        if not self._search_grounding:
            raise LLMError("Research requires a search-enabled client.")
        try:
            researched = request_with_retry(
                "llm_research", contents=research_prompt,
                config={"tools": [{"google_search": {}}], "max_output_tokens": self._max_output_tokens,
                        "thinking_config": {"thinking_budget": 0},
                        "http_options": {"timeout": max(60000, int(self._timeout_seconds * 1000))}},
            )
            self._record_research_usage(researched)
            candidates = getattr(researched, "candidates", None) or []
            raw_metadata = getattr(candidates[0], "grounding_metadata", None) if candidates else None
            chunks = getattr(raw_metadata, "grounding_chunks", None) or []
            metadata = self._extract_grounding_metadata(researched)
            if not metadata or not metadata.sources or not any(getattr(c, "web", None) for c in chunks):
                raise LLMError("Research returned no source citations; JSON extraction was skipped.")
            research_text = getattr(researched, "text", None)
            if not research_text:
                raise LLMError("Research returned no evidence text.")
            self._last_grounding_metadata = metadata
            self._last_sources = list(metadata.sources)
            evidence = {"text": research_text, "sources": [asdict(s) for s in metadata.sources],
                        "supports": [asdict(s) for s in metadata.supports]}
            self.last_research_evidence = evidence
            extraction_prompt = {
                "task": "Extract only facts present in the supplied research evidence into the schema. Do not research, use memory, invent values or infer missing prices. Use null or empty arrays for missing facts. source_urls/source_url must use the exact supplied citation URLs supporting that entity or offer. Source indices in supports refer to the sources array. Never assign an unrelated source just to fill a field. Preserve the exact book, selection, line, odds and observation time. Convert American odds to decimal only if explicitly observed. Follow the schema enum spellings. Return one JSON object.",
                "request": research_prompt, "schema": schema, "evidence": evidence,
            }
            extracted = request_with_retry(
                "llm_extraction", contents=json.dumps(extraction_prompt),
                config={"response_mime_type": "application/json", "max_output_tokens": self._max_output_tokens,
                        "thinking_config": {"thinking_budget": 0}, "temperature": 0,
                        "http_options": {"timeout": max(60000, int(self._timeout_seconds * 1000))}},
            )
            self._record_research_usage(extracted)
            result = _parse_first_json_object(_extract_json_text(extracted.text or ""))
            if not isinstance(result, dict):
                raise LLMError("Research extraction did not return an object.")
            return result
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Grounded research failed ({type(exc).__name__}).") from exc

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
            if rendered:
                for match in re.finditer(r'href="(https?://[^"]+)"', rendered):
                    url = match.group(1)
                    if url not in {s.url for s in sources}:
                        sources.append(GroundingSource(url=url, title=url.split("/")[2]))
        if sources:
            return sources
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

    @diagnostic_stage("llm_generate", provider="gemini")
    def generate_structured(
        self, *, system_prompt: str, user_prompt: str, schema: dict, temperature: float | None = None
    ) -> dict:
        prompt = f"{system_prompt}\n\n{user_prompt}\n\nRespond with valid JSON only."
        attempts = self._max_retries + 1

        for attempt in range(1, attempts + 1):
            try:
                with provider_attempt("gemini", attempt=attempt, model=self._model):
                    config: dict[str, Any] = {
                        "max_output_tokens": self._max_output_tokens,
                        "thinking_config": {"thinking_budget": 0},
                    }
                    if temperature is not None:
                        config["temperature"] = temperature
                    if self._search_grounding:
                        config["tools"] = [{"google_search": {}}]
                        config["http_options"] = {"timeout": max(60000, round(self._timeout_seconds * 1000))}
                    else:
                        config["response_mime_type"] = "application/json"
                    response = self._client.models.generate_content(
                        model=self._model,
                        contents=prompt,
                        config=config,
                    )

                    parsed: dict | None = None
                    candidates = getattr(response, "candidates", None) or []
                    parts = getattr(getattr(candidates[0], "content", None), "parts", None) if candidates else None

                    # If multiple candidate parts exist (e.g. from Google Search Grounding), evaluate each part first
                    if parts and len(parts) > 1:
                        for part in parts:
                            p_text = getattr(part, "text", None)
                            if p_text and p_text.strip():
                                extracted = _extract_json_text(p_text)
                                try:
                                    candidate_parsed = _parse_first_json_object(extracted)
                                    if isinstance(candidate_parsed, dict):
                                        parsed = candidate_parsed
                                        break
                                except (json.JSONDecodeError, ValueError, LLMError):
                                    pass

                    if parsed is None:
                        try:
                            text = response.text
                        except (ValueError, AttributeError):
                            text = None
                        if not text and parts:
                            text = _best_json_part(parts)
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
                    usage = getattr(response, "usage_metadata", None)
                    if usage:
                        p_tokens = getattr(usage, "prompt_token_count", 0) or 0
                        c_tokens = getattr(usage, "candidates_token_count", 0) or 0
                        t_tokens = getattr(usage, "total_token_count", 0) or 0
                        self._last_token_usage = TokenUsage(
                            prompt_tokens=p_tokens,
                            completion_tokens=c_tokens,
                            total_tokens=t_tokens,
                        )
                        self._cumulative_tokens[0] += p_tokens
                        self._cumulative_tokens[1] += c_tokens
                        self._cumulative_tokens[2] += t_tokens
                        emit("provider.usage", provider="gemini", model=self._model,
                             prompt_tokens=p_tokens, completion_tokens=c_tokens, total_tokens=t_tokens,
                             source_count=len(self._last_sources))
                    else:
                        self._last_token_usage = None
                    return parsed
            except json.JSONDecodeError as exc:
                if attempt >= attempts:
                    raise LLMError(f"Gemini returned invalid JSON: {exc}") from exc
                prompt += (
                    "\n\nYour previous response was not valid JSON. "
                    "Retry now with exactly one JSON object and no explanation, citations, or markdown."
                )
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
                retry_delay = self._retry_delay_seconds * (2 ** (attempt - 1))
                self._sleep(min(retry_delay, 60.0))
                continue
            except Exception as exc:
                error_str = str(exc)
                retryable = any(
                    code in error_str
                    for code in (
                        "429",
                        "RESOURCE_EXHAUSTED",
                        "504",
                        "DEADLINE_EXCEEDED",
                        "503",
                        "UNAVAILABLE",
                        "502",
                        "BAD_GATEWAY",
                        "timed out",
                        "Timeout",
                        "ConnectTimeout",
                        "ReadTimeout",
                    )
                )
                if retryable:
                    if attempt >= attempts:
                        raise LLMError(error_str) from exc
                    retry_delay = self._retry_delay_seconds * (2 ** (attempt - 1))
                    self._sleep(min(retry_delay, 60.0))
                    continue
                raise LLMError(error_str) from exc

        raise LLMError("Gemini provider failed without returning data")
