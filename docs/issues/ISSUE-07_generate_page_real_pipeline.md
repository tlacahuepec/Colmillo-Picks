---
name: TDD + SOLID Work Item
about: Generate Page: Verify Real Discovery & Pick Pipeline
labels: ["tdd-done", "frontend", "picks"]
---

## Goal
Verify and ensure complete end-to-end functionality of `GeneratePage.tsx`: match discovery, manual match configuration across all 4 sports, async pick execution, status polling with progress indicator, markdown report rendering, and PrizePicks availability checks.

## Acceptance Criteria
- [x] User can click "Discover Today's Matches" and see fixtures grouped by sport.
- [x] Clicking "Use Match" populates the manual form with home/away teams and date.
- [x] Submitting the form calls `api.createPick()`, polls `api.getPickStatus()` until completion, and displays the full markdown report.
- [x] Checks PrizePicks availability via `api.checkAvailability()` and renders status badges (`Available`, `Line Differs`, `Not Available`).
- [x] "View Diagnostics" deep-links to the Diagnostics Hub passing `operation_id`.

## Tests to write first (RED)
- [x] Integration/UI: Form submission initiates `createPick` and transitions into polling state.
- [x] Polling: Terminal status `success` displays `<MarkdownRenderer />` with the generated report.
- [x] Failure-path tests: Terminal status `failed` displays the `error_stage` and `error_message` in an `<Alert severity="error">`.

## Implementation Plan (GREEN)
1. Verify sport-specific market selectors for Baseball (8 MLB props) and NFL market groupings.
2. Ensure polling intervals terminate on timeout (max 300s) or terminal state.
3. Test with live backend or MSW mocks in tests.

## Refactor/Design Notes (REFACTOR)
- SRP: Ensure `GeneratePage.tsx` delegates markdown rendering to `MarkdownRenderer.tsx`.
- DIP: Decouple polling logic into a custom hook `usePickPolling` if necessary.

## Out of Scope
- Adding new sports beyond Soccer, Basketball, Baseball, and NFL.

## Definition of Done
- [x] All pick generation and discovery flows verified against backend contracts.
