---
name: TDD + SOLID Work Item
about: History Page: Real Hit Rate & Grading Persistence
labels: ["tdd-done", "frontend", "history"]
---

## Goal
Ensure `HistoryPage.tsx` displays live paginated pick history, allows filtering by sport, calculates aggregate hit rates via `api.getHitRate()`, replays generated reports, and persists user-graded outcomes (`win`, `loss`, `push`, `void`) via `api.recordOutcomes()`.

## Acceptance Criteria
- [x] Displays paginated list of runs from `GET /picks`.
- [x] Sport selector filters historical runs cleanly.
- [x] Outcome grading form allows grading individual player props.
- [x] Submitting grades executes `POST /picks/{id}/outcomes` and reloads updated hit rate statistics.
- [x] Hit rate summary card displays win percentage, decided count, and W/L breakdown.

## Tests to write first (RED)
- [x] Integration/UI: `HistoryPage.test.tsx` verifying pick selection loads details and outcome inputs.
- [x] Outcomes persistence: Changing prop outcome to "win" and clicking save posts to `/picks/{id}/outcomes`.

## Implementation Plan (GREEN)
1. Verify `HistoryPage.tsx` handles empty outcome lists gracefully.
2. Ensure outcome submission triggers a hit rate refresh.
3. Test pagination controls (Next / Prev buttons).

## Refactor/Design Notes (REFACTOR)
- SRP: Separate outcome grading form into a sub-component if needed.

## Out of Scope
- Pick deletion features.

## Definition of Done
- [ ] History list and outcome grading verified against backend contracts.
