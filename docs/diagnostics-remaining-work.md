# Diagnostics: remaining work

Updated September 11, 2026. This is the active handoff checklist.

Local implementation and verification are complete. The final full regression
suite passed **1,610 tests** and the local benchmark met all three overhead
targets. Changes remain uncommitted. The architecture and user instructions
are saved in [diagnostics.md](diagnostics.md), and the accepted scope is tracked
in [diagnostics-implementation-plan.md](diagnostics-implementation-plan.md).

## Finish local verification

- [x] Collect the full regression-suite result and resolve any failures:
  **1,610 passed**, 217 dependency deprecation warnings, 159.78 seconds.
- [x] Run focused regressions for the final review fixes: canonical operation
  lookup, storage failures, partial outcomes, safe summary fallback and UI guidance.
- [x] Run the final benchmark with request-logging middleware included, after
  the regression suite stops. Record pipeline/API latency, process memory,
  delivery counters and the limits of the stubbed workload.
- [x] Save the benchmark evidence in [diagnostics-validation.md](diagnostics-validation.md).
- [x] Finish CLI/test-isolation checks and the final full-suite confirmation.
- [x] Update the final regression evidence and the
  main implementation checklist.
- [x] Complete the final lint and whitespace/diff review. Confirm no credentials,
  generated databases or unrelated changes are included.

## Next step: create the PR

- [ ] **Create a pull request after implementation and verification.**
- [ ] Check the base and branch history first: this work currently sits on
  `feat/nfl-support`; the PR should contain the diagnostics change without
  duplicating NFL work already merged into the target branch.
- [ ] Include the user-facing behavior, architecture guide, validation evidence
  and deployment limitations in the PR description.

Creating the PR is the next task. Local implementation and verification are
complete; no deployment has been performed.

## After review and deployment

- [ ] Confirm API, worker and CLI use the intended persistent diagnostics path.
  Compose/Render configuration points diagnostics at `/var/data/diagnostics.db`.
- [ ] Verify the existing business database and run-ledger paths are persistent;
  back up historical files before relocating any of them.
- [ ] Check diagnostics health and access with normal and administrator keys.
- [ ] Run one real query, open its Diagnostics page, inspect the stage timeline,
  and download its sanitized ZIP.
- [ ] Observe latency, memory and dropped-event/storage counters under real
  traffic. The local benchmark does not establish production overhead.

## Known boundaries to retain in the handoff

- The original Saints–Lions collector cause was discarded; historical evidence
  cannot be reconstructed or its outcome silently corrected.
- Queued diagnostics are best effort. Crashes, overflow and retention can remove
  detail; completeness notices and compact business summaries describe the gap.
- The 128 MiB budget limits logical database use; WAL and filesystem allocation
  can add physical disk usage.
- The viewer refreshes manually. A UI timeout can leave the backend running.
- Normal users share sanitized access through the existing app key; technical
  frames and temporary metadata-only debugging require the administrator key.
- SQLite supports the current shared local-storage deployment. A deployment
  across multiple hosts needs a shared storage adapter.
- Earlier regression tests used the regular `data/runs.db` path and may have
  appended synthetic entries. The fixture now isolates test ledgers. Review
  possible test entries separately; no automatic deletion without a reliable
  baseline that preserves real history.
