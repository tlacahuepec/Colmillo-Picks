---
name: TDD + SOLID Work Item
about: Fix VS Code Launch & Dev Tasks Configuration
labels: ["tdd-done", "dev-tools"]
---

## Goal
Fix the VS Code launch and task labels so developers can press F5 or use Visual Studio Code to launch the full-stack FastAPI backend and modern React UI without task name mismatches or errors.

## Acceptance Criteria
- [x] In `.vscode/launch.json`, `"preLaunchTask"` points to a valid task defined in `.vscode/tasks.json` (`"Start React UI Only"` or equivalent).
- [x] The compound configuration `"Full Stack: Debug API + Launch UI"` cleanly starts the FastAPI API on port 8000 and the modern UI on port 5173 without manual intervention.
- [x] VS Code Tasks list includes a clear task to execute quality checks (Pytest + Ruff + React tests).

## Tests to write first (RED)
- [x] Integration/UI: Verify running the VS Code launch configuration or `run-dev.ps1 -React` starts without process exit code 1.
- [x] Failure-path tests: Verify port conflict handling gracefully frees ports 8000 and 5173.

## Implementation Plan (GREEN)
1. Edit `.vscode/launch.json` line 26: Change `"preLaunchTask": "Start Modern UI (Vite)"` to `"preLaunchTask": "Start React UI Only"`.
2. Verify `run-dev.ps1` correctly passes the `-React` flag and launches both `uvicorn` and `npm run dev`.
3. Test F5 launch in VS Code.

## Refactor/Design Notes (REFACTOR)
- SRP: Keep VS Code configuration declarative and delegate process management to `run-dev.ps1`.
- DIP/abstractions: Keep port definitions synchronized with `.env.example`.

## Out of Scope
- Modifying Dockerfile or production deployment pipelines.

## Definition of Done
- [ ] All new/changed behavior covered by tests or verified in VS Code.
- [ ] No unrelated refactors.
