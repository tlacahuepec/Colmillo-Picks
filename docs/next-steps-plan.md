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

### Track 1: Release v0.9.0 Delivery (Immediate Priority)
1. **Branch & Commit**: Create `chore/v0.9.0-governance-and-release-prep` from `dev`, commit the 3 files, and push.
2. **Pull Request to dev**: Open PR to `dev` with title `chore: v0.9.0 governance alignment and changelog cut`.
3. **Squash Merge**: Merge to `dev` using squash merge.
4. **Release Branch**:
   ```bash
   git checkout dev && git pull
   git checkout -b release/v0.9.0
   git tag v0.9.0-rc.1
   git push origin release/v0.9.0 --tags
   ```
5. **CI Verification**: Ensure the `release-readiness` job passes on GitHub Actions.
6. **Deploy & Tag**: Squash merge `release/v0.9.0` into `main` and tag `v0.9.0`.

---

### Track 2: Catalog Subsystem Staged Rollout (Shadow Mode → Primary)
1. **Scheduler & Storage Verification**: Validate background job scheduler (`services/catalog/scheduler.py`) and SQLite lease mechanism under simulated load.
2. **Freshness & Selective Refresh**: Test field-level freshness policies (`services/catalog/freshness.py`) ensuring stale fields trigger targeted refreshes while valid records are read from cache.
3. **Performance Benchmarking**: Benchmark response latency and API call volume for catalog-first reads (`services/catalog/read_service.py`) versus live pipeline generation.
4. **Production Activation**: Transition `COLMILLO_CATALOG_SHADOW_MODE` from `true` to `false` in staging, verify diagnostics error rates, and promote to production.

---

### Track 3: Data Feeds & Resolving Open Spikes (#248 & #250)
1. **Provider Proof of Value**: Execute evaluation gate per `docs/market-source-research.md` using an authorized odds aggregator (e.g. The Odds API or SportsGameOdds).
2. **Odds Provider Port**: Implement normalized provider adapter in `services/catalog/providers.py` to ingest real-time lines.
3. **Scoring Integration**: Feed observed prop lines into `baseball_scoring.py` and `basketball_scoring.py` to eliminate `missing_prop_lines` rejections.
4. **Spike Closure**: Re-run `scripts/audit_sport_reliability.py` across 10 games per sport to complete acceptance criteria for #250 and #248.

---

### Track 4: Progressive Type Safety Expansion
1. **Test Policy Update**: Update `tests/test_pyright_config.py` to allow additional type-clean modules.
2. **Diagnostics Inclusion**: Add `services/diagnostics.py` to `pyrightconfig.json` (currently 0 errors).
3. **Services Annotations**: Progressively type-annotate `services/api/` and `services/worker/main.py`.

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
