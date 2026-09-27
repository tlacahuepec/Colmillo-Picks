---
name: TDD + SOLID Work Item
about: History Page: Component & Outcomes Tests
labels: ["tdd-done", "frontend", "testing"]
---

## Goal
Implement component tests in `frontend/src/pages/HistoryPage.test.tsx` verifying pick listing, sport filtering, pagination, markdown report replay, and outcome grading.

## Acceptance Criteria
- [x] Tests rendering historical pick list from MSW.
- [x] Tests sport filter dropdown triggers `api.listPicks(..., sport)`.
- [x] Tests selecting a pick displays markdown report and original request parameters.
- [x] Tests grading a pick outcome and submitting updates the status.

## Tests to write first (RED)
- [x] Unit/Component: `HistoryPage.test.tsx` covering all acceptance criteria.

## Implementation Plan (GREEN)
1. Write tests in `HistoryPage.test.tsx` with MSW handlers.
2. Confirm hit rate card assertions.
3. Run `npm test` to verify GREEN.

## Refactor/Design Notes (REFACTOR)
- SRP: Keep outcome mock data organized in test fixtures.

## Out of Scope
- Backend database testing.

## Definition of Done
- [ ] `HistoryPage.test.tsx` passes with 100% test success.
