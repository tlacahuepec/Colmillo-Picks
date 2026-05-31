# Spike: Reduce flakiness in basketball Gemini enrichment for marginal/future games

**Parent:** Epic #219 — Cross-sport observability & no-silent-mock-fallback hardening  
**Type:** Spike (time-boxed investigation + prototype)  
**Suggested labels:** `spike`, `basketball`, `enrichment`, `tdd-red`, `observability`  
**Suggested assignees:** (the person who just reproduced the flakiness)

---

## Problem (live reproduction, 2026-05-30)

We executed the **exact same basketball request** twice, ~5 minutes apart, via the real API + background worker:

```json
POST /picks
{
  "sport": "basketball",
  "home_team": "okc",
  "away_team": "sas",
  "event_date": "2026-05-30",
  "markets": ["assists", "threes", "points", "rebounds"],
  "top_n": 5
}
```

**Run 1** (`f485a4be-90f2-477b-9d78-ef3e021fe837`):
- `basketball_gemini_enrichment_attempt` (huge duplicated missing_fields list for Tre Jones, Devin Vassell, Keldon Johnson, Cason Wallace, Chet Holmgren, Luguentz Dort)
- `basketball_gemini_enrichment_success` ("enriched_players": 6, "enriched_line_players": 2)
- Immediately followed by `basketball_scoring_rejected reason=missing_player_context`
- Final: `pipeline_run_failed` at `score` stage with:
  > "Could not find enough match details: missing basketball player context for requested markets."

**Run 2** (`5c428bba-e582-45ad-ad3b-3d4374a32016`, same inputs):
- Enrichment produced enough of the critical numeric fields.
- `score` stage succeeded.
- 5 real scored picks returned (including Shai Gilgeous-Alexander etc.).

**Persisted evidence** (in `colmillo.db` `picks_history`):
- Both rows have identical `request_json`.
- One has `status=failed`, `error_stage=score`, 0 scores.
- The other has `status=success`, 5 scores.

This is the exact flakiness introduced while dogfooding the #219 basketball path.

---

## Root Cause Analysis (from live logs + code review)

The enrichment path lives in:
- `skills/soccer-prop-picks/scripts/missing_input_enrichment.py`
  - `_build_system_prompt()` + `_build_user_prompt()` (very strict "never fabricate", "only verified sources", "null when unknown")
  - `required_json_shape` (vague on basketball stats: `"all_required_stats": "sport-specific numeric fields..."`)
  - `GeminiMissingInputEnrichmentProvider.enrich_missing_inputs()` — single call to `client.generate_structured()`
  - `merge_enriched_inputs()` + `_normalize_line()` (drop anything without source metadata)
- `basketball_module.py:27` — `_MARKET_REQUIRED_FIELDS` (the real contract the scoring gate enforces)
- `llm/gemini_client.py:122` — `generate_structured()` has no `temperature` param, hard-coded config, only retries on transient/JSON errors.
- `sport_module.py` — where the `GeminiMissingInputEnrichmentProvider` is wired (only when Gemini key present).

The combination of:
- Future date (no real grounding possible)
- Extremely strict prompt rules
- Single LLM sample
- No temperature variation or best-of-N selection

...means success is non-deterministic for marginal cases.

The strictness is **correct** for the #219 goal (no silent fake data). The UX for games we *do* want to support is too brittle.

---

## Proposed Spike Work (two concrete improvements)

### 1. Improve the prompt + `required_json_shape` for basketball numeric fields

- Make the schema explicitly reference the fields from `_MARKET_REQUIRED_FIELDS`:
  - `minutes_proj`, `usage_rate`
  - `{points,rebound,assist,threes}_avg`, `{points,rebound,assist,threes}_last5`
  - `three_point_attempts`
- Add basketball-specific guidance, a small "good example" object, per-field confidence, and clear instructions for future-dated games ("synthesize plausible values **only** when you have strong recent-team context; always label confidence appropriately").
- Keep the "do not fabricate PrizePicks lines / injuries / lineups" rules strong.
- Update `merge_enriched_inputs` / the response mapper if the new shape gives us richer data we currently ignore.

### 2. Add "best-of-N" (or temperature-varied retry) fallback **only in the enrichment path**

- Introduce support (in `GeminiMissingInputEnrichmentProvider` or a thin wrapper) for N attempts.
- Vary temperature (or use a "creative vs strict" prompt variant) on retries.
- After all attempts, pick the "best" result using a simple, deterministic heuristic:
  - Highest number of populated fields from `_MARKET_REQUIRED_FIELDS`
  - Highest average confidence
  - Fewest critical nulls
- Log the winner (`attempt=2/3`, `temperature=0.9`, `fields_gained=...`) under the existing `basketball_gemini_enrichment_*` events.
- Store the decision in `data_quality` / `collection_summary`.
- First attempt should still use the strict prompt + low/zero temperature (when the client supports it).
- Later attempts may use a slightly relaxed prompt variant that still forbids fabrication of betting lines.
- This must **not** affect the main `LLMGameProvider` / `LLMPlayerStatsProvider` / `LLMPropsProvider` paths.

**Non-goals for the spike:**
- Changing any scoring thresholds or re-introducing silent placeholders.
- Touching baseball or soccer enrichment yet.
- Full production config for N/temperature (just a working prototype + tests).

---

## Spike Acceptance Criteria (what "done" looks like)

- [ ] Small spike branch + PR created from this story.
- [ ] Prompt + `required_json_shape` in `missing_input_enrichment.py` now gives the LLM explicit basketball numeric field guidance + examples.
- [ ] `enrich_missing_inputs` (or new `BestOfNEnrichmentWrapper`) supports N attempts with temperature variation and selects the richest valid result.
- [ ] All changes follow TDD (new tests written first). Unit tests mock the LLM client and assert selection logic + prompt content.
- [ ] One new test (or updated integration test) reproduces a "marginal data" scenario and shows improved success rate.
- [ ] `ruff check .` + relevant pytest paths are green.
- [ ] The exact OKC/SAS 2026-05-30 scenario (or a synthetic equivalent) now succeeds in ≥4/5 runs in a manual loop (without weakening the no-fake-data contract).
- [ ] Rich observability is preserved or improved (attempt number, chosen temperature, fields gained, winner rationale all logged).
- [ ] This issue is closed by merging the spike PR (per repo rules).

**Spike timebox:** 1–2 focused days. Output = working prototype + tests + recommendation for the real implementation (or "this approach isn't worth it").

---

## Reproduction for the spike (use this exact request)

See the JSON at the top of this file. Run it 5+ times in a row (or in a small loop) against a clean `GEMINI_API_KEY` environment. Measure success rate of reaching `score` success vs. `missing_player_context` rejection before vs. after your changes.

---

## Suggested Implementation Notes (for the person who picks up the spike)

- Extend the `LLMClient` protocol (or add an optional `generation_params` dict) so the enrichment path can request different temperatures.
- The Gemini client already has a retry loop — extending it for best-of-N with different configs is natural.
- Keep changes small and localized to the enrichment module + one client tweak.
- SOLID: consider a small `EnrichmentStrategy` or just a helper function for the selection heuristic.

---

## Links & Evidence

- Failed run in DB: `f485a4be-90f2-477b-9d78-ef3e021fe837`
- Successful run in DB: `5c428bba-e582-45ad-ad3b-3d4374a32016`
- Detailed logs from the flaky run (see the conversation that produced this spike)
- `_MARKET_REQUIRED_FIELDS` — `skills/soccer-prop-picks/scripts/basketball_module.py:27`
- Enrichment code — `skills/soccer-prop-picks/scripts/missing_input_enrichment.py`
- Gemini client — `skills/soccer-prop-picks/scripts/llm/gemini_client.py:122`

**Created as a direct follow-up to live debugging of Epic #219 basketball path on 2026-05-30.**

---

*When implementing, follow the repo rules: TDD (tests first), small changes, run `ruff check`, no failing tests left, update this issue on the PR, and close via merge.*