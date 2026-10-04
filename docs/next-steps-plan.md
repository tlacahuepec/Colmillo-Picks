# Roadmap and Next Steps Plan

Last updated: September 12, 2026.
This document outlines the active roadmap and prioritized work tracks for Colmillo-Picks following the governance, changelog, and diagnostics type-safety alignment.

---

## Current Checkpoint

The following files have been prepared and verified:
1. `CHANGELOG.md` — Packaged unreleased changes into milestone `0.9.0` (2026-09-12) covering Catalog foundation, Diagnostics, NFL support, LangGraph, and toolchain configurations.
2. `docs/branch-strategy.md` — Reconciled release merge policy with the active GitHub squash-only ruleset, documenting administrator emergency bypass.
3. `services/diagnostics.py` — Added explicit typing to contextvars and modernized `duration_ms` type guards.

---

## Prioritized Execution Tracks

### Track 1: Release v0.9.0 Delivery (Completed — September 12, 2026)
1. **Branch & Commit**: Created `chore/v0.9.0-governance-and-release-prep` from `dev`, committed files, and pushed.
2. **Pull Request to dev**: Opened [PR #344](https://github.com/tlacahuepec/Colmillo-Picks/pull/344) (`chore: v0.9.0 governance alignment and changelog cut`).
3. **Squash Merge**: Merged PR #344 to `dev` using squash merge.
4. **Release Branch & RC**: Created `release/v0.9.0`, tagged `v0.9.0-rc.1`, pushed branch and tags. Verified pre-release workflow and artifacts.
5. **CI Verification**: `release-readiness` and full CI suite passed cleanly on GitHub Actions.
6. **Deploy & Tag**: Opened [PR #345](https://github.com/tlacahuepec/Colmillo-Picks/pull/345) to merge `release/v0.9.0` into `main`, verified checks, squash merged, and tagged stable `v0.9.0`. Verified stable release artifacts and published Docker images on GHCR.

---

### Track 2: Catalog Subsystem Staged Rollout (Shadow Mode → Primary) (Completed — October 3, 2026)
1. **Scheduler & Storage Verification**: Validated background job scheduler (`services/catalog/scheduler.py`) and SQLite lease mechanism under concurrent load with multi-threaded claim stress tests, lease expiry recovery, heartbeat renewal, and crash recovery. Added `CatalogStore.find_snapshot` and typed contract deserializers.
2. **Freshness & Selective Refresh**: Tested field-level freshness policies (`services/catalog/freshness.py`) ensuring stale fields trigger targeted refreshes while valid records are read from cache, covering all TTL categories, hierarchical field prefixes, and clock skew.
3. **Performance Benchmarking**: Benchmarked catalog-first reads (`services/catalog/read_service.py`) versus live pipeline generation with `scripts/benchmark_catalog_reads.py`, demonstrating ~1.2ms cache hits (>5,000x speedup vs live LLM generation) and 100% token savings.
4. **Slate Pipeline Activation**: Wired `CatalogFirstReader` into slate orchestration (`services/api/main.py`) with configurable rollout modes (`COLMILLO_CATALOG_READ_MODE`: `shadow` default, `catalog_first`, `live`) recording catalog telemetry in match runs.

---

### Track 3: Data Feeds & Resolving Open Spikes (#248 & #250) (Completed — October 4, 2026)
1. **Odds Provider Port & Adapter**: Implemented `TheOddsApiAdapter` in `services/catalog/odds_provider.py` conforming to `CatalogProvider(Protocol)` with live HTTP query support, header quota tracking (`x-requests-remaining`), and hermetic deterministic replay.
2. **MLB Prop Lines Port & Ingestion**: Defined `MLBPropLinesPort` in `mlb_provider_ports.py` and implemented `MLBPropLinesAdapter`. Wired prop lines ingestion into `MLBCollectionService` (`mlb_collection.py`) and `_build_baseball_module()` in `sport_module.py`.
3. **Basketball Prop Lines Adapter**: Implemented `BasketballPropLinesAdapter` in `basketball_prop_lines_adapter.py` providing points, rebounds, assists, and threes lines; wired into `_build_basketball_module()`.
4. **Spike Closure & Reliability Verification**: Re-ran `scripts/audit_sport_reliability.py` across baseball and basketball fixtures, reducing baseball scoring rejections from 100% (10/10 `missing_prop_lines` in prior audit) to 0% (100% scoring success, 5 scored picks per fixture). Documented proof of value and closed spikes #248 and #250 in `docs/spikes/odds-provider-proof-of-value-2026-10-04.md`.

---

### Track 4: Progressive Type Safety Expansion (Completed — October 3, 2026)
1. **Config & Diagnostics Gate**: Added `services/diagnostics.py` to `pyrightconfig.json`, configured `extraPaths` for skills scripts, and updated policy test in `tests/test_pyright_config.py`. Fixed `valid_request_id` (`TypeGuard[str]`), `sentry.py` typing, and resolved a silent `ImportError` bug in worker outcome resolution ([PR #359](https://github.com/tlacahuepec/Colmillo-Picks/pull/359)).
2. **SQLAlchemy 2.0 Typed Models**: Migrated all 5 ORM models in `services/api/db.py` to `Mapped[T] = mapped_column(...)`, added strict schema regression test in `tests/api/test_db_schema.py`, and eliminated over 200 Pyright errors ([PR #360](https://github.com/tlacahuepec/Colmillo-Picks/pull/360)).
3. **Full Services Gate**: Resolved all residual type errors in `services/api/main.py` and `services/api/diagnostics_routes.py`, gated `services/api` and `services/worker` in `pyrightconfig.json` (0 errors), and updated CI enforcement.

---

## Session Resumption Commands
```powershell
# Check git status
git status

# Run full test suite
pytest -q

# Run linters and type checkers
ruff check .
pyright
```
