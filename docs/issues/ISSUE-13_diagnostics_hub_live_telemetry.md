---
name: TDD + SOLID Work Item
about: Diagnostics Hub: Strip Mock Fallbacks & Wire Live Telemetry
labels: ["tdd-done", "frontend", "diagnostics"]
---

## Goal
Remove all hardcoded mock fallbacks and fake KPI metrics from `frontend/src/pages/DiagnosticsPage.tsx`, wiring it completely to live backend routes (`/diagnostics/health`, `/diagnostics/operations`, `/export`).

## Acceptance Criteria
- [x] Remove hardcoded KPI metrics (99.8% health, 98.0% freshness, etc.) and replace with real counters from `/diagnostics/health` and `/admin/stats`.
- [x] Remove `loadMockDiagnostics()` fallback; if the backend query fails, display an explicit error alert with retry option.
- [x] Ensure selecting an operation displays real telemetry stages, durations, and error classifications.
- [x] "Prepare diagnostic ZIP" downloads a live sanitized ZIP from `GET /diagnostics/operations/{id}/export`.

## Tests to write first (RED)
- [x] Integration/UI: `DiagnosticsPage.test.tsx` verifying operations load from API.
- [x] Failure-path tests: API 500 error displays `<Alert severity="error">` and does NOT load fake fallback data.

## Implementation Plan (GREEN)
1. Delete `loadMockDiagnostics()` from `DiagnosticsPage.tsx`.
2. Wire KPI cards to `api.getDiagnosticHealth()`.
3. Test sanitized ZIP export functionality.
4. Add component tests in `DiagnosticsPage.test.tsx`.

## Refactor/Design Notes (REFACTOR)
- SRP: Redact secrets on the frontend as an additional layer of defense before rendering summaries.

## Out of Scope
- Modifying backend telemetry storage logic.

## Definition of Done
- [ ] Diagnostics page runs 100% on live API telemetry.
