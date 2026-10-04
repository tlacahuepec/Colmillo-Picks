# Migration Issues Backlog

This folder contains the complete set of TDD + SOLID work items created to migrate from the legacy Streamlit UI to the modern React 19 UI.

Each issue is isolated and sized to allow **2 or 3 autonomous agents** to work concurrently without merge conflicts.

## Issues Index

| Issue | Title | Scope | Status | Target Files |
|---|---|---|---|---|
| [ISSUE-01](./ISSUE-01_fix_vscode_launch_tasks.md) | Fix VS Code Launch & Dev Tasks Configuration | Config & Dev Experience | **Done** (TDD Green) | `.vscode/launch.json`, `.vscode/tasks.json` |
| [ISSUE-02](./ISSUE-02_setup_vitest_testing_library.md) | Add Vitest & React Testing Library Infrastructure | Frontend Test Framework | **Done** (TDD Green) | `frontend/package.json`, `frontend/vite.config.ts` |
| [ISSUE-03](./ISSUE-03_fix_vite_proxy_routes.md) | Fix Vite Proxy Routes for Stats & Availability | Network & Reverse Proxy | **Done** (TDD Green) | `frontend/vite.config.ts` |
| [ISSUE-04](./ISSUE-04_frontend_api_client_tests.md) | Unit Test Frontend API Client with MSW | API Client & Resilience | **Done** (TDD Green) | `frontend/src/api/client.ts`, `frontend/src/api/client.test.ts` |
| [ISSUE-05](./ISSUE-05_backend_enrichment_audit_endpoint.md) | Implement Backend Endpoint for Grounding Audit | Backend API Support | **Done** (TDD Green) | `services/api/main.py`, `tests/api/test_enrichment_audit.py` |
| [ISSUE-06](./ISSUE-06_appshell_dynamic_hit_rate.md) | Wire AppShell Live Win Rate & API Health | App Shell & Global State | **Done** (TDD Green) | `frontend/src/components/Layout/AppShell.tsx`, `AppShell.test.tsx` |
| [ISSUE-07](./ISSUE-07_generate_page_real_pipeline.md) | Generate Page: Verify Real Discovery & Pick Pipeline | Core Pick Generation | **Done** (TDD Green) | `frontend/src/pages/GeneratePage.tsx` |
| [ISSUE-08](./ISSUE-08_generate_page_component_tests.md) | Generate Page: Component & Async Polling Tests | UI Tests | **Done** (TDD Green) | `frontend/src/pages/GeneratePage.test.tsx` |
| [ISSUE-09](./ISSUE-09_best_today_batch_availability.md) | Best Today: Fix Batch Availability & Slate Status Display | Multi-Sport Slates | **Done** (TDD Green) | `frontend/src/pages/BestTodayPage.tsx` |
| [ISSUE-10](./ISSUE-10_best_today_component_tests.md) | Best Today: Component & Slate Detail Tests | UI Tests | **Done** (TDD Green) | `frontend/src/pages/BestTodayPage.test.tsx` |
| [ISSUE-11](./ISSUE-11_history_page_grading_persistence.md) | History Page: Real Hit Rate & Grading Persistence | History & Outcomes | **Done** (TDD Green) | `frontend/src/pages/HistoryPage.tsx` |
| [ISSUE-12](./ISSUE-12_history_page_component_tests.md) | History Page: Component & Outcomes Tests | UI Tests | **Done** (TDD Green) | `frontend/src/pages/HistoryPage.test.tsx` |
| [ISSUE-13](./ISSUE-13_diagnostics_hub_live_telemetry.md) | Diagnostics Hub: Strip Mock Fallbacks & Wire Live Telemetry | Diagnostics & Tracing | **Done** (TDD Green) | `frontend/src/pages/DiagnosticsPage.tsx`, `DiagnosticsPage.test.tsx` |
| [ISSUE-14](./ISSUE-14_catalog_grounding_strip_mocks.md) | Catalog & Grounding Audit: Remove Mock Fallbacks | Developer Tools | **Done** (TDD Green) | `frontend/src/pages/CatalogPage.tsx`, `GroundingAuditPage.tsx` |
