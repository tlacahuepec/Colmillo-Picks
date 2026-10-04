---
name: TDD + SOLID Work Item
about: Implement Backend Endpoint for Grounding Audit
labels: ["tdd-done", "backend", "api"]
---

## Goal
Implement a dedicated backend endpoint `POST /enrichment/audit` in `services/api/` matching the contract expected by `GroundingAuditPage.tsx`, allowing the UI to audit LLM search grounding without hardcoded mocks.

## Acceptance Criteria
- [x] Endpoint `POST /enrichment/audit` registered in FastAPI router requiring `X-API-Key`.
- [x] Accepts request payload: `{ num_players: int, num_attempts: int, use_bible_style: bool }`.
- [x] Runs the grounding quality audit pipeline (from `scripts/audit_grounding_quality.py`) or mock adapter in dry-run mode.
- [x] Returns structured response: `{ summary, players, sources, bible_expected }`.
- [x] Covered by automated tests in `tests/api/test_enrichment_audit.py`.

## Tests to write first (RED)
- [x] Unit/Integration: `tests/api/test_enrichment_audit.py` calling `TestClient(app).post("/enrichment/audit", json=...)`.
- [x] Assert status 200 with valid schema.
- [x] Assert 401 when `X-API-Key` is missing.

## Implementation Plan (GREEN)
1. Write failing test in `tests/api/test_enrichment_audit.py`.
2. Add Pydantic request and response schemas in `services/api/`.
3. Add router endpoint in `services/api/main.py` delegating to `audit_grounding_quality`.
4. Run `pytest tests/api/test_enrichment_audit.py` to confirm GREEN.

## Refactor/Design Notes (REFACTOR)
- SRP: Keep audit execution in a service module, not directly in the router definition.
- DIP: Inject LLM client provider interface for easy test mocking.

## Out of Scope
- Rewriting the underlying Gemini search grounding logic.

## Definition of Done
- [ ] Endpoint passes backend unit tests.
- [ ] Added to Swagger docs at `/docs`.
