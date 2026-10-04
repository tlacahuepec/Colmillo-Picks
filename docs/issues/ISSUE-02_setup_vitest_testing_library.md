---
name: TDD + SOLID Work Item
about: Add Vitest & React Testing Library Infrastructure
labels: ["tdd-done", "frontend", "testing"]
---

## Goal
Equip the React 19 application (`frontend/`) with a modern, high-speed test suite using Vitest, `@testing-library/react`, and Mock Service Worker (MSW), enabling TDD and regression assertions.

## Acceptance Criteria
- [x] `frontend/package.json` includes `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, and `msw` in devDependencies.
- [x] `npm test` script runs Vitest in CI/single-run mode; `npm run test:watch` runs in interactive watch mode.
- [x] Vitest is configured in `frontend/vite.config.ts` or `frontend/vitest.config.ts` with `environment: 'jsdom'` and a global test setup file.
- [x] A sample test (`frontend/src/App.test.tsx`) renders the shell and passes.

## Tests to write first (RED)
- [x] Unit: Add `frontend/src/setupTests.ts` importing `@testing-library/jest-dom`.
- [x] Integration/UI: Create `frontend/src/App.test.tsx` asserting the brand title "ColmilloPicks" renders in the document.

## Implementation Plan (GREEN)
1. Add testing dependencies to `frontend/package.json`.
2. Configure Vitest in `frontend/vite.config.ts`.
3. Create `frontend/src/setupTests.ts`.
4. Add `test` and `test:watch` scripts to `frontend/package.json`.
5. Run `npm test` and ensure green status.

## Refactor/Design Notes (REFACTOR)
- SRP: Keep test configuration separated from production bundling.
- DIP/abstractions: Use MSW for network mocking rather than mocking global `fetch` directly in each test file.

## Out of Scope
- Writing tests for individual pages (handled in subsequent dedicated issues).

## Definition of Done
- [ ] `npm test` executes and succeeds cleanly.
- [ ] Documented in README or developer docs.
