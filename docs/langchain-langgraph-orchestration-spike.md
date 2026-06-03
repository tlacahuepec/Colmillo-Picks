# LangChain / LangGraph Pipeline Orchestration Spike

Issue: [#242](https://github.com/tlacahuepec/Colmillo-Picks/issues/242)  
Date: 2026-06-03  
Scope: decision document only; no production framework adoption in this change.

## Executive Summary

Recommendation: defer broad adoption, keep the current deterministic pipeline runner as the default, and pilot LangGraph only around LLM explanation/enrichment control flow if we need richer retries, branching, or traceable state transitions.

Colmillo's pipeline is already intentionally small and deterministic: `collect -> score -> rank`, with sport modules owning data collection and scoring. That shape does not yet justify replacing the core orchestration layer with LangChain or LangGraph. The highest-value opportunity is narrower: the LLM enrichment boundary already has a prompt -> model -> parser -> merge pattern, and the repository already contains lightweight proof-of-concept adapters (`LangChainEnricher` and `SimpleLangGraphFlow`) that exercise those concepts without adding runtime dependencies.

Decision:

- Keep the current approach for core sport pipeline orchestration.
- Do not add LangChain as a broad dependency for the entire app today.
- Pilot LangGraph for the LLM explanation/enrichment step only if upcoming work requires conditional validation, fallback routing, resumable retries, or detailed state transition traces.
- Revisit after 2-3 real provider integrations or one incident where current step telemetry is insufficient.

## Research Sources

Primary sources checked on 2026-06-03:

- [LangChain overview](https://docs.langchain.com/oss/python/langchain/overview): LangChain is positioned as an agent framework for model, tool, prompt, and middleware composition, with standardized model interfaces and LangSmith tracing.
- [LangChain model docs](https://docs.langchain.com/oss/python/langchain/models): chat models support standalone calls, streaming, batching, structured output/tool calling capabilities, provider swapping, and configurable retry/timeout parameters.
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview): LangGraph is a low-level orchestration framework/runtime for long-running, stateful agents with durable execution, streaming, human-in-the-loop, persistence, and LangSmith observability.
- [LangSmith observability concepts](https://docs.langchain.com/langsmith/observability-concepts): traces represent one operation and contain runs/spans for prompt formatting, LLM calls, parsers, retrieval, or other units of work.

Research assumptions:

- This decision treats sports pipeline orchestration and LLM call orchestration separately. A framework can be useful at the LLM boundary while still being unnecessary for deterministic sport scoring.
- The spike intentionally avoids benchmarking runtime overhead because no production dependency is added and the current repository already has no framework-backed implementation to benchmark.
- The recommendation should be revisited when live provider fan-out, provider fallback, or LLM retry/validation complexity grows beyond simple Python control flow.

## Current Colmillo Pipeline Fit

Current implementation shape:

1. API receives a sport-aware pick request and delegates non-soccer sports through a shared runner.
2. `PipelineRunner` calls the selected `SportModule` using a deterministic `collect -> score -> rank` sequence.
3. Sport-specific modules own provider integration, scoring, explanations, report rendering, and guardrails.
4. LLM enrichment is already isolated behind provider adapters and deterministic schema validation.
5. Existing tests validate the lightweight LangChain-style and LangGraph-style prototypes without requiring external framework packages.

Implications:

- Core orchestration is not agentic yet. It has no open-ended planning loop, tool-selection loop, multi-turn memory, or human-in-the-loop checkpoint.
- Most failures are simple stage failures (`collect` or `score`) where explicit Python control flow is easy to read, test, and debug.
- Current observability already includes stage timelines, traces, provider status, run ledgers, and report-level notes.
- The most framework-like area is explanation/enrichment because it combines prompt building, provider invocation, schema validation, fallback behavior, and merge semantics.

## Option Comparison

| Option | Pros | Cons | Fit for Colmillo now |
|---|---|---|---|
| LangChain | Standard model interfaces; provider swapping; prompt/model/parser composition; tool integration; structured output support; LangSmith tracing can capture model and parser runs. | Adds dependency surface and integration-package churn; abstraction can hide provider-specific behavior; much of the current deterministic code would become less direct; current Gemini-only flow does not need broad provider abstraction yet. | Good for a narrow model-call adapter or future multi-provider LLM experiments. Low value as a replacement for the core pipeline runner. |
| LangGraph | Maps well to stateful step transitions, conditional routing, fallback branches, retries/checkpoints, and traceable graph execution; could make LLM validation/fallback paths explicit. | More framework complexity than the current three-stage runner needs; graph state schemas and node wiring add overhead; dependency/version churn; possible duplicate telemetry unless integrated carefully with current traces and ledgers. | Good candidate for a small pilot around LLM enrichment or multi-provider collection workflows. Not justified for full pipeline orchestration today. |
| Current approach | Minimal dependencies; clear Python control flow; easy unit testing; explicit domain boundaries; no framework lock-in; current step telemetry already captures collect/score timings and failures. | Manual retry and branch logic can grow messy; no built-in graph visualization/checkpointing; prompt/model/parser tracing must be implemented manually or via direct LangSmith SDK instrumentation. | Best default for the current deterministic pipeline. Continue using it while extracting small interfaces where future framework pilots can plug in. |

## Highest-Value Pipeline Stages

1. Most likely to benefit: LLM explanation/enrichment.
   - Why: this stage already follows the composable sequence `prompt_builder -> chat_model -> structured_parser -> merge`.
   - LangChain value: standardized model interfaces and structured output support could simplify future provider swaps if OpenAI/Anthropic/Gemini are all active.
   - LangGraph value: explicit graph nodes for prepare context, invoke model, validate output, fallback, and merge would make conditional routing and failure recovery visible.
   - Guardrail: preserve deterministic fallback and schema validation as separate domain functions, not framework-specific code.

2. Most likely to benefit: provider collection when multiple live providers are enabled.
   - Why: live stats, odds, lineup, weather, and availability providers may need conditional routing, partial fallback, retries, and cache-aware decisions.
   - LangGraph value: graph state could represent provider status, stale-data gates, and fallback routes across providers.
   - Guardrail: do not make data providers agent-selected. Provider order and fallback should remain deterministic and testable.

## Recommendation

Recommendation: defer broad adoption.

Do not add LangChain as a broad dependency and do not replace `PipelineRunner` with LangGraph for the full pipeline. The present collect/score/rank flow is too deterministic and compact to justify a new orchestration framework.

Recommended next step if the team wants hands-on learning:

1. Keep the existing lightweight prototypes as the reference shape.
2. Add a feature-flagged, non-default LangGraph pilot only for LLM explanation/enrichment.
3. Require fixture-backed unit tests proving identical successful outputs and identical deterministic fallback behavior before enabling the pilot anywhere beyond local experimentation.
4. Measure whether the framework improves at least one concrete pain point: retry policy clarity, state transition debugging, provider swap effort, or trace quality.

Adoption threshold:

- Adopt narrowly if the pilot reduces custom orchestration code or improves trace/debug quality without weakening deterministic guardrails.
- Defer again if the pilot mostly wraps existing pure functions without reducing complexity.
- Pass entirely if future work remains limited to one LLM provider and no complex branch/retry requirements.

## Follow-up Notes

- Add no production dependencies from this spike. A spike should not alter deploy-time dependency risk without an implementation story.
- If LangSmith is desired for observability, evaluate direct LangSmith SDK instrumentation separately; LangSmith can trace non-LangChain applications, so it does not require adopting LangChain/LangGraph first.
- If a future LangGraph pilot is approved, keep graph nodes as thin wrappers around existing pure functions. That keeps TDD simple and avoids framework lock-in.
- Track provider call latency, retry count, fallback path, schema validation failures, and final merge result in the existing run trace before comparing against LangSmith traces.
- Dependency risk should be reviewed on every framework upgrade because LangChain/LangGraph integration packages evolve quickly.

## Decision Log

- 2026-06-03: Spike completed. Decision is to defer broad adoption, keep current pipeline orchestration, and consider only a narrow LangGraph pilot for LLM explanation/enrichment or provider collection fallback once concrete complexity appears.
