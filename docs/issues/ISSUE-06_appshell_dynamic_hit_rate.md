---
name: TDD + SOLID Work Item
about: Wire AppShell Live Win Rate & API Health
labels: ["tdd-done", "frontend", "layout"]
---

## Goal
Replace the hardcoded `"68.4% Win Rate"` chip in `frontend/src/components/Layout/AppShell.tsx` with live data fetched from `api.getHitRate()`, updating dynamically when outcomes are recorded.

## Acceptance Criteria
- [x] `AppShell.tsx` queries `api.getHitRate()` on mount.
- [x] When `hit_rate` is available, renders percentage (e.g. `(hit_rate * 100).toFixed(1) + "% Win Rate"`).
- [x] When no decided picks exist, renders `"No graded picks"` or `"N/A Win Rate"` gracefully.
- [x] Listens for an outcome update event or refetches on tab changes to keep the metric live.

## Tests to write first (RED)
- [x] Integration/UI: `AppShell.test.tsx` asserting the win rate chip renders `"75.0% Win Rate"` when API returns `hit_rate: 0.75`.
- [x] Failure-path tests: Assert that if `/stats/hit-rate` errors, the chip falls back to `"No graded picks"` without crashing the app.

## Implementation Plan (GREEN)
1. Add state in `AppShell.tsx` for `hitRate`.
2. Add `useEffect` querying `api.getHitRate()`.
3. Update the Chip label to use the real state value.
4. Verify in `AppShell.test.tsx`.

## Refactor/Design Notes (REFACTOR)
- SRP: Extract a small `WinRateBadge` component if needed.

## Out of Scope
- Adding historical date picker to the header.

## Definition of Done
- [ ] Hardcoded `"68.4% Win Rate"` removed completely.
- [ ] Tests pass in Vitest.
