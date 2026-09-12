# Diagnostics implementation and progress

Owner: Colmillo-Picks. Agreed September 11, 2026.

**PR created: [#308](https://github.com/tlacahuepec/Colmillo-Picks/pull/308). Next: CI and review.**
Do not deploy this change or rewrite historical run outcomes automatically.

## Accepted design

An in-app Diagnostics page explains application failures without requiring a
terminal or raw JSON reading. Coverage includes every sport, API, worker, CLI,
discovery, provider calls, and UI connectivity. Any app user can inspect sanitized
records; technical frames and temporary debugging require the administrator key.
No new paid monitoring service is required.

Producers emit versioned, allowlisted metadata into a bounded in-process queue.
A background writer batches events into a separate SQLite database on persistent
storage. Existing business records retain compact outcomes when detailed logging
is unavailable. Operation IDs link request, queue job, pick/slate, and ledger IDs.
Outcomes distinguish successful results, partial results, valid no-picks results,
and actual failure. Legacy polling statuses remain compatible.

Default limits: 30 days of detail, 90 days of summaries, 128 MiB logical budget,
8 KiB/event, 500 events/operation, 2,000 queue entries with reserved critical
capacity, 100-event batches, 100 ms idle writer wakeup, 15-minute admin debug window.
Overflow and retention are visible; complete delivery during a crash is not promised.

Never record prompts, responses, HTML, request bodies, credentials, cookies,
environment dumps, signed URLs, arbitrary user strings, or traceback locals.
Keep error codes, exception/cause types, bounded code frames for admins, timings,
provider/model identity, counts, missing-field categories, retries and cache state.
Debug mode follows the same metadata-only policy.

## Delivery checklist

- [x] Shared metadata/error model, operation context, bounded background storage.
- [x] Additive durable operation/outcome fields and connected API job records.
- [x] NFL collector failures preserve cause information and fail explicitly.
- [x] Shared pipeline and provider instrumentation; CLI and worker integration.
- [x] Diagnostics list/detail/events/export and administrator routes.
- [x] In-app viewer, navigation links, sanitized ZIP and local connection reports.
- [x] Complete API/privacy/retention/fault regression verification: 1,610 tests passed.
- [x] Measure enabled/disabled latency and memory overhead: local targets passed.
- [x] Document operation and review final diff; lint and whitespace checks passed.
- [x] **Create PR** with validation evidence and deployment limitations: [#308](https://github.com/tlacahuepec/Colmillo-Picks/pull/308).
- [ ] Complete CI and review before merging.
- [ ] Deploy after review; confirm persistent paths and one real run in Diagnostics.

Implementation notes and user instructions: [Diagnostics guide](diagnostics.md).
Measured verification results: [Validation record](diagnostics-validation.md).
Active handoff: [Remaining work](diagnostics-remaining-work.md).

## Acceptance gates

1. NFL provider exception produces `failed` with preserved classified cause;
   legitimate zero recommendations produce `no_picks`. Mixed results stay partial.
2. IDs do not leak between threads/jobs. Missing historical evidence stays unknown.
3. API/export/Sentry privacy tests exclude secrets and raw research, including old
   traces. Administrator authorization is independent of ordinary app access.
4. Overflow, storage errors, interruption, expiry and pruning are visible and do
   not prevent generation. Diagnostic reads use separate rate limits.
5. A user can navigate from a failed query to its explanation and download a report.
6. Against identical stubbed workloads, target less than 5% p95 pipeline overhead,
   less than 10 ms added p95 API latency, and less than 32 MiB added process memory.
   Record actual measurements and workload limitations; do not claim zero overhead.

## Historical incident

The Saints–Lions run at 2026-09-11 05:04 UTC saved an empty successful result after
its collector exception was discarded. Its original provider cause is unknown.
A server error in a different smoke run is not proof of this run's cause. New
diagnostics must not fabricate a historical exception or silently backfill status.
