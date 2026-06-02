# Improvement: Add best-of-N / temperature-varied sampling to Gemini missing-input enrichment (basketball + baseball)

**Source:** Review of PR #229 ("Dev" → main) + live dogfooding findings  
**Epic:** #219 (Cross-sport observability & hardening)  
**Suggested labels:** `enhancement`, `observability`, `basketball`, `baseball`, `Epic #219`  
**Priority for next release:** High (makes the new enrichment capability actually reliable)

---

## Context from PR #229

PR #229 delivered the first real integration of `GeminiMissingInputEnrichmentProvider` into the baseball path, along with the supporting observability plumbing (`error_details_json`, rich failure logging, etc.) and logging robustness fixes.

This is great forward progress on Epic #219.

However, during live debugging of the exact same basketball request run multiple times (`OKC @ SAS 2026-05-30`), we observed persistent flakiness:

- One run logged `basketball_gemini_enrichment_success` (6 players, 2 lines) but still failed the strict scoring gate with `missing_player_context`.
- An identical request 5 minutes later succeeded with real scored picks.
- Root cause: single LLM call + strict "never fabricate / only verified sources" prompt + future or marginally-grounded dates = non-deterministic completeness of the required numeric fields (`usage_rate`, `*_last5`, `minutes_proj`, `three_point_attempts`, etc.).

The enrichment logic landed in #229 (and the earlier basketball path) is single-shot. When the first (and only) call returns "good but not good enough" data, the run fails even though enrichment "worked."

---

## Proposed Improvement

Add a lightweight, opt-in **"best-of-N" (or temperature-varied) sampling mechanism** that lives **only inside the missing-input enrichment path**.

### Core Behavior
- Support a small number of attempts (N=3 is a good default for a spike).
- First attempt uses the current strict prompt + conservative settings.
- Subsequent attempts can vary temperature (when the client supports it) or use a narrowly relaxed prompt variant that still forbids fabrication of lines, injuries, lineups, etc.
- After all attempts, deterministically pick the "best" result using a simple, auditable heuristic:
  - Highest number of populated fields from the sport's `_MARKET_REQUIRED_FIELDS`
  - Highest average `confidence`
  - Fewest critical nulls in scoring-critical stats
- Log the outcome clearly under the existing `*_gemini_enrichment_*` events (include attempt number, temperature used, why this result won).
- Record the decision in the new rich `error_details` / `data_quality` structures (so it is visible in the API and persisted runs).

### Scope (keep it small and safe)
- Only affects the enrichment step (`GeminiMissingInputEnrichmentProvider` and its callers in basketball/baseball modules).
- Does **not** change the primary game/stats/props providers.
- Does **not** relax the "no silent fake data for user-facing picks" contract — the first attempt remains strict.
- Minimal extension to the `LLMClient` protocol / Gemini client only if temperature needs to be exposed.

---

## Why This Is a Real, High-Value Improvement for the Next Release

- Turns the foundation delivered in PR #229 from "sometimes magically great" into "reliably useful on marginal and future-dated games."
- Directly solves the exact flakiness we reproduced in production dogfooding (OKC/SAS 2026-05-30 runs).
- High observability leverage — we already have excellent logging and the new error context from #229.
- Low risk, high signal: easy to A/B or feature-flag at the enrichment provider level.
- Natural follow-up to the spike document we created after reviewing PR #229 (`docs/spikes/spike-2026-05-30-basketball-enrichment-flakiness.md`).

---

## Acceptance Criteria

- [ ] `enrich_missing_inputs` (or a thin `ResilientEnrichmentProvider` wrapper) supports configurable N attempts with temperature (or prompt variant) variation.
- [ ] Clear, deterministic winner-selection logic + rich logging of the decision.
- [ ] TDD: Unit tests (written first) that mock the LLM client and assert selection behavior, logging, and fallback to the first strict result when all attempts are poor.
- [ ] At least one integration-style test per sport exercising the "first attempt insufficient, later attempt wins" scenario.
- [ ] The decision is visible in the new `error_details` structures introduced in PR #229.
- [ ] No change to the strict anti-fabrication rules on the primary (first) attempt.
- [ ] Works for both basketball and the new baseball enrichment path.
- [ ] Updated documentation or spike notes as needed.

---

## Suggested Implementation Notes

- Start in `missing_input_enrichment.py`.
- Consider adding a small `best_of_n` parameter (with sensible default) to `GeminiMissingInputEnrichmentProvider`.
- Expose temperature support through the existing `GeminiLLMClient` (it already has retry logic — this is a natural extension).
- Keep the selection heuristic simple and deterministic so behavior is reproducible and debuggable.
- Wire the winner metadata into the rich context that PR #229 made possible.

---

## Related Work

- Epic #219
- Spike created after PR #229 review: `docs/spikes/spike-2026-05-30-basketball-enrichment-flakiness.md`
- Live reproduction: OKC vs SAS 2026-05-30 runs (failed vs successful identical requests)
- Changes in PR #229: baseball enrichment integration, `error_details_json` plumbing, logging robustness

---

**This is a concrete, scoped, high-ROI follow-up that takes the good work in PR #229 and makes the new enrichment capability production-ready and reliable.**

When creating the GitHub issue, copy everything below the title as the body and use the suggested labels. Pull the issue in progress immediately per repo rules.