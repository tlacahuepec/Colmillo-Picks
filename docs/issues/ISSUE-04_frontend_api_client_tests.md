---
name: TDD + SOLID Work Item
about: Unit Test Frontend API Client with MSW
labels: ["tdd-done", "frontend", "api-client"]
---

## Goal
Implement thorough unit test coverage for `frontend/src/api/client.ts` using MSW, testing authentication headers (`X-API-Key`), query string construction, error handling, and payload parsing across all endpoints.

## Acceptance Criteria
- [x] Test coverage for: `discoverMatches`, `createPick`, `getPick`, `getPickStatus`, `checkAvailability`, `listPicks`, `recordOutcomes`, `getHitRate`, `createSlate`, `getSlate`, `listDiagnostics`, `exportDiagnostic`.
- [x] Verifies `X-API-Key` is attached from localStorage or falls back to `"dev-key"`.
- [x] Verifies 4xx and 5xx API errors extract `detail` message and throw descriptive `Error`.
- [x] Verifies blob export handles binary stream responses.

## Tests to write first (RED)
- [x] Unit: `frontend/src/api/client.test.ts` testing successful responses for each method.
- [x] Failure-path tests: Assert that HTTP 400 with `{ "detail": "Invalid sport" }` throws `Error: Invalid sport`.
- [x] Failure-path tests: Assert that HTTP 401 Unauthorized throws `Error: HTTP 401: Unauthorized`.

## Implementation Plan (GREEN)
1. Set up MSW server in `frontend/src/mocks/server.ts` and handlers in `handlers.ts`.
2. Write unit tests in `frontend/src/api/client.test.ts`.
3. Assert header injection and error message formatting.
4. Run `npm test` to verify 100% pass rate.

## Refactor/Design Notes (REFACTOR)
- SRP: Keep MSW handlers organized by endpoint domain (picks, slates, diagnostics, catalog).
- DIP: Keep `request()` helper clean and testable in isolation.

## Out of Scope
- React component rendering tests.

## Definition of Done
- [ ] `frontend/src/api/client.test.ts` passes with full method coverage.
