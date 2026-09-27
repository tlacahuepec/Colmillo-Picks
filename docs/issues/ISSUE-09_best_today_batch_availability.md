---
name: TDD + SOLID Work Item
about: Best Today: Fix Batch Availability & Slate Status Display
labels: ["tdd-done", "frontend", "slates"]
---

## Goal
Ensure `BestTodayPage.tsx` reliably creates cross-sport slates, polls for completion, lists past slates, executes batch availability checks via `/availability/check-batch`, and displays risk flags and candidate rankings without mock dependencies.

## Acceptance Criteria
- [x] User can configure sports, date, max matches per sport, and top-N candidates.
- [x] Submitting executes `api.createSlate()`, returning 202 Accepted.
- [x] Polling displays real-time progress until the slate is completed.
- [x] Clicking "Check Availability" calls `api.checkAvailabilityBatch()` and updates candidate cards with platform lines and status badges.
- [x] Candidate cards display normalized scores, kickoff time, and risk flags.

## Tests to write first (RED)
- [x] Integration/UI: `BestTodayPage.test.tsx` verifying slate submission and candidate rendering.
- [x] Failure-path tests: Partial failures (e.g. some matches waiting for lineups) display partial failure alert badges without crashing.

## Implementation Plan (GREEN)
1. Verify `BestTodayPage.tsx` payload matches backend `SlateRequest` schema.
2. Confirm `checkAvailabilityBatch` maps returned badges by `(player, market)`.
3. Handle partial pipeline statuses gracefully.

## Refactor/Design Notes (REFACTOR)
- SRP: Candidate card rendering can be cleanly separated into a `SlateCandidateCard` sub-component.

## Out of Scope
- Modifying backend slate scoring algorithms.

## Definition of Done
- [x] Slate generation and batch availability work end-to-end against live backend and MSW mocks.
