---
name: TDD + SOLID Work Item
about: Best Today: Component & Slate Detail Tests
labels: ["tdd-done", "frontend", "testing"]
---

## Goal
Implement automated component tests in `frontend/src/pages/BestTodayPage.test.tsx` verifying slate submission, polling, recent slates selection, candidate rendering, and batch availability badge updates.

## Acceptance Criteria
- [x] Tests form submission with selected sports and date.
- [x] Tests candidate table rendering: rank, player name, line, normalized score, and confidence badge.
- [x] Tests clicking "Check Availability" triggers `POST /availability/check-batch` and renders resulting badges.
- [x] Tests selecting a past slate from recent slates list loads its candidate details.

## Tests to write first (RED)
- [x] Unit/Component: `BestTodayPage.test.tsx` covering slate lifecycle and batch availability interactions.

## Implementation Plan (GREEN)
1. Write tests in `BestTodayPage.test.tsx` using MSW.
2. Verify token summary formatting and execution latency display.
3. Confirm tests pass with `npm test`.

## Refactor/Design Notes (REFACTOR)
- SRP: Keep slate test fixtures in `frontend/src/mocks/fixtures/slates.ts`.

## Out of Scope
- Direct backend database testing.

## Definition of Done
- [x] `BestTodayPage.test.tsx` passes cleanly.
