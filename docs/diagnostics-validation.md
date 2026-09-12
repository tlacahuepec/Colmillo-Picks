# Diagnostics validation

Recorded September 11, 2026, on the local Windows development environment.
Changes remain uncommitted and have not been deployed.

## Regression checks

- Final full suite: **1,610 passed**, 217 dependency deprecation warnings,
  159.78 s. Command: `.\.venv\Scripts\python.exe -m pytest -q`.
- Final review regressions: **227 passed**, including UI interactions, storage,
  API, partial outcomes, slate execution and worker resolution.
- Production logging branch: **11 API diagnostics tests passed**, including a
  subprocess that installs Uvicorn's real logging configuration and verifies
  uncaught exception payloads cannot bypass redaction.
- Final CLI-output and test-database isolation checks: **56 passed**, 4 warnings,
  9.90 s. The existing local business and run-ledger files retained their prior
  modification times during these tests.
- The full suite passed as recorded above. A subsequent file check caught two
  integration tests that explicitly cleared their inherited environment. Their
  isolation was corrected; **all 10 tests in those two files passed** in 0.84 s,
  with the local business and run-ledger modification times unchanged.
- Final `python -m ruff check .` and `git diff --check`: **passed**.

The new coverage exercises NFL collector cause chains, valid zero-pick results,
thread-context isolation, canonical IDs after later resolution, queue overflow,
event caps, expiry/pruning, dead process leases, SQLite locking and recovery,
disabled collection, metadata-only debug windows, normal/admin authorization,
sanitized exports/Sentry/console output, legacy summaries and UI failure reports.
Streamlit interactions are exercised through `AppTest`; no live browser or real
provider/deployment smoke run has been performed.

## Local overhead benchmark

Command from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_diagnostics.py --samples 200
```

| Measurement | Result | Target |
| --- | --- | --- |
| Pipeline p95 without diagnostics | 82.453 ms | Baseline |
| Pipeline p95 with diagnostics | 83.828 ms | Less than 5% overhead |
| Relative pipeline p95 overhead | **1.67%** | Less than 5% |
| Added API p95 latency | **1.555 ms** | Less than 10 ms |
| Added process peak memory | **5.449 MiB** | Less than 32 MiB |
| Added traced Python peak allocations | 0.208 MiB | Supporting measurement |
| Dropped events / write failures observed | **0 / 0** | Inspect for loss |

The benchmark returned `pass: true`. It uses 200 operations per mode, four
concurrent workers, four 20 ms stub stages per operation, provider metadata events
and a temporary SQLite database. Alternating batches reduce ordering bias. Forty
requests per mode exercise FastAPI/TestClient; the enabled app includes request
middleware and JSON log formatting, with output discarded instead of rendered.
The snapshot captured 36 queued events before orderly shutdown, so queue depth
does not mean those records were lost.

Allocation tracing runs in a separate 40-operation pass because the profiler
changes Python execution costs. Process memory includes test-harness growth.
Diagnostic console output is disabled during the benchmark. This measures local
stubbed work, not live provider requests, persistent-disk performance in hosting,
network latency or production traffic. Re-measure after deployment; these results
do not promise zero overhead or prove production performance.

## Test data and handoff

The final test fixture isolates the default run ledger and diagnostics paths,
including CLI subprocesses. Some earlier regression tests used the existing
`data/runs.db`, so it may contain synthetic test entries. No automatic cleanup is
being performed without a reliable baseline that separates them from real runs.

See [remaining work](diagnostics-remaining-work.md). **Create the PR next**, then
validate persistent paths, real query visibility and performance after review and
deployment. The original discarded Saints–Lions exception remains unknown.
