---
name: TDD + SOLID Work Item
about: Fix Vite Proxy Routes for Stats & Availability
labels: ["tdd-done", "frontend", "network"]
---

## Goal
Update `frontend/vite.config.ts` reverse proxy settings to include `/stats` and `/availability`, eliminating 404 connection errors when the frontend queries hit rates or checks batch prop availability.

## Acceptance Criteria
- [x] Requests from the frontend to `/stats/hit-rate` proxy to `http://localhost:8000/stats/hit-rate`.
- [x] Requests from the frontend to `/availability/check-batch` proxy to `http://localhost:8000/availability/check-batch`.
- [x] Cross-Origin requests continue to respect `COLMILLO_UI_ORIGIN` on the backend.

## Tests to write first (RED)
- [x] Integration/UI: Verify proxy configuration object in `frontend/vite.config.ts` includes keys `"/stats"` and `"/availability"`.
- [x] E2E/Manual: Trigger `api.getHitRate()` and `api.checkAvailabilityBatch([])` through dev server and assert 200/valid HTTP responses.

## Implementation Plan (GREEN)
1. Edit `frontend/vite.config.ts`.
2. Add `"/stats": "http://localhost:8000"` and `"/availability": "http://localhost:8000"` under `server.proxy`.
3. Verify dev server proxies requests correctly without path stripping.

## Refactor/Design Notes (REFACTOR)
- SRP: Group all proxy target configurations cleanly.

## Out of Scope
- Modifying backend CORS middleware.

## Definition of Done
- [ ] All new/changed proxy routes verified with active dev server.
