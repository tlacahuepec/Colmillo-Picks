# Issue Actions Following Merge of PR #229 (into main)

**Date:** 2026-05-31  
**Context:** PR #229 ("Dev" batch, 38 commits) has been merged to `main`. This landed a large portion of Epic #219 work (enrichment, observability/error_details, logging hardening, baseball changes, soccer fallback disabling, etc.).

## 1. Close Completed Stories

### Issue #224 — S03: Add Gemini fallback enrichment for missing basketball/baseball scoring inputs
**Status:** Completed by the dev batch (PR #225 merged to dev, now in #229 → main).

**Ready-to-post closure comment (copy-paste):**

```
Closing as completed.

The core acceptance criteria for Gemini enrichment fallback (basketball + baseball) were implemented in the dev batch (PR #225) and have now been merged to main via PR #229.

- Baseball now has enrichment provider support + loop in `score()`.
- Observability (error_details, rich logging of failures) landed as part of the same batch.
- Guardrails and structured output expectations from the story are in place.

Any remaining polish (e.g. the best-of-N resilience improvement) is tracked in the follow-up issue #230.

Refs: PR #229, Epic #219.
```

**Action for maintainer:** 
- Go to https://github.com/tlacahuepec/Colmillo-Picks/issues/224
- Close the issue with the comment above (or similar).
- Label: `completed` or remove `bug`/`tdd-red` if desired.

---

## 2. Next to Work On (Recommended)

**Top recommendation: Issue #230**  
"Add best-of-N / temperature-varied sampling to Gemini missing-input enrichment (basketball + baseball)"

**Why this one makes the most sense right now:**
- Directly born from the review of the just-merged PR #229 + real production flakiness we debugged (OKC/SAS 2026-05-30 runs).
- It is a small, focused, TDD-friendly spike (exactly the style the repo demands).
- High value: makes the new enrichment capability (just landed in #229) reliable instead of flaky on marginal/future games.
- Perfect continuation of Epic #219 without opening huge new epics.
- We already have a detailed spike doc (`docs/spikes/spike-2026-05-30-basketball-enrichment-flakiness.md`) and improvement proposal (`docs/improvements/post-pr229-enrichment-resilience.md`).

**Immediate action (pull in progress per repo rules):**

Ready-to-post comment for #230:

```
Pulled in progress per repository rules (Claude.md + contributor playbook).

This is the direct high-ROI follow-up identified during review of PR #229 (the dev batch that just merged).

Starting TDD spike:
1. RED tests for best-of-N selection + temperature variation in the enrichment path.
2. Minimal implementation in `missing_input_enrichment.py` + small Gemini client extension if needed.
3. Integration test exercising the "first attempt marginal, later attempt wins" scenario.
4. Rich logging + wiring into the new `error_details` structures from #229.

Will keep changes small, follow SOLID, run ruff + full relevant tests on every step, and close via squash-merged PR.

Refs: PR #229, Epic #219, spike doc in repo.
```

**Action:** 
- Add the above comment to https://github.com/tlacahuepec/Colmillo-Picks/issues/230
- Optionally assign yourself.
- Create a branch from main: `spike/best-of-n-enrichment-resilience` or `feat/enrichment-best-of-n-230`

---

## Other Open Issues (Quick Assessment)

- **#219 (main Epic)**: Leave open. Many child stories were advanced or completed by #229. Use it as the parent for new work like #230.
- **#226 (Engineering Constitution Compliance)**: Good process cleanup item. Consider after #230 if you want to address tech debt (pyright, ruff config, branch naming discipline). Lower urgency than making the new enrichment reliable.
- **#207 / #212 / #213 (Best Today epic)**: Future feature work. Depends on #62 (availability). Defer until core #219 hardening + reliability is solid.
- **#208 / #214 (Discord spike)**: Separate evaluation. Not blocking current path.
- Older items (#62 availability UI, etc.): Still relevant but lower priority than stabilizing what was just shipped in #229.

---

## Suggested Immediate Workflow (following your rules exactly)

1. Close #224 using the comment above.
2. Pull #230 in progress with the comment above.
3. Start the spike on a properly named branch.
4. Follow TDD (tests first), small changes, ruff on every step, full test runs, proper PR template when ready.
5. Close #230 via a squash-merged PR that references this analysis.

This keeps momentum on the real reliability gap exposed by the recent merge while respecting all process rules.

**Local tracking file:** `docs/improvements/issue-actions-after-pr229.md` (this document).
