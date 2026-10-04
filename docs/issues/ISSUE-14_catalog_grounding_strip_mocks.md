---
name: TDD + SOLID Work Item
about: Catalog & Grounding Audit: Remove Mock Fallbacks
labels: ["tdd-done", "frontend", "developer-tools"]
---

## Goal
Remove mock fallback intercepts from `CatalogPage.tsx` and `GroundingAuditPage.tsx` / `frontend/src/api/client.ts`, wiring both pages exclusively to real API responses.

## Acceptance Criteria
- [x] In `frontend/src/api/client.ts`, remove the `.catch()` fallback returning mock NBA player audit data in `runGroundingAudit()`.
- [x] In `CatalogPage.tsx`, remove mock event fallbacks (`nba:event:20260913-001`, etc.); render real events from `api.listCatalogEvents()` and real snapshot payloads from `api.getCatalogSnapshot()`.
- [x] Network failures on both pages render honest error states with retry buttons.

## Tests to write first (RED)
- [x] Integration/UI: `CatalogPage.test.tsx` verifying real events render.
- [x] Failure-path tests: Network error triggers error message instead of fallback mock data.

## Implementation Plan (GREEN)
1. Remove `.catch()` simulation block from `client.ts:runGroundingAudit`.
2. Clean `CatalogPage.tsx` of hardcoded synthetic scenarios.
3. Wire honest loading and error displays.
4. Verify with `npm test`.

## Refactor/Design Notes (REFACTOR)
- SRP: Keep developer tools clean and aligned with backend schemas.

## Out of Scope
- Adding new catalog sports.

## Definition of Done
- [ ] Mock fallbacks stripped from both screens.
