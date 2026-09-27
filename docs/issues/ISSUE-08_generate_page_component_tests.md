---
name: TDD + SOLID Work Item
about: Generate Page: Component & Async Polling Tests
labels: ["tdd-done", "frontend", "testing"]
---

## Goal
Create a comprehensive test suite `frontend/src/pages/GeneratePage.test.tsx` verifying user interactions, validation errors, sport selection, async polling lifecycles, and availability badge rendering.

## Acceptance Criteria
- [x] Tests form validation: Missing home or away team displays validation feedback.
- [x] Tests sport switching: Switching to Baseball updates market options to MLB props (hits, strikeouts, etc.).
- [x] Tests match discovery: Mocked `/matches/discover` populates match buttons; clicking one sets form values.
- [x] Tests polling lifecycle: Steps through `pending` -> `running` -> `success` using fake timers or MSW sequences.
- [x] Tests error display when pipeline fails.

## Tests to write first (RED)
- [x] Unit/Component: `GeneratePage.test.tsx` test cases covering the acceptance criteria above.

## Implementation Plan (GREEN)
1. Write tests in `GeneratePage.test.tsx` using `@testing-library/react` and MSW.
2. Fix any minor state or accessibility bugs uncovered during testing.
3. Verify all tests pass with `npm test`.

## Refactor/Design Notes (REFACTOR)
- SRP: Keep mock payloads in a separate fixture file `frontend/src/mocks/fixtures/picks.ts`.

## Out of Scope
- Backend execution testing.

## Definition of Done
- [x] `GeneratePage.test.tsx` passes with high branch coverage.
