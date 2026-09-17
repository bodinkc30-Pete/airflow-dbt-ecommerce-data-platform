# Postmortem: PostgreSQL advisory-lock contention drill (synthetic)

| Field | Value |
| --- | --- |
| Incident date | 2026-09-09 |
| Severity | SEV3 (synthetic drill, staging-equivalent local PostgreSQL) |
| Status | Resolved |
| Detected at | 2026-09-09, via the read-only diagnostics snapshot (`load_postgres_diagnostics`) showing `wait_event_type = Lock` after the 1-second long-running threshold |
| Resolved at | 2026-09-09, seconds after containment |
| Time to recover | Seconds (drill-scoped; not a production MTTR sample) |
| Author | Data engineering |
| Related alert IDs | None — drill was detected by direct diagnostics, not by a fired alert |
| Evidence | `tests/failure/test_postgres_advisory_lock_incident.py`, `src/ecommerce_pipeline/reliability/postgres_diagnostics.py`, `docs/runbooks/failure_injection_runbook.md` |

## Summary

A failure-injection drill simulated lock contention: one connection held a
project-reserved PostgreSQL advisory lock while a second connection requested
the same lock and blocked. The diagnostics layer detected the blocker mapping
and the lock wait, the drill released only its own lock, and the blocked
operation completed. Recovery was verified by a fresh diagnostics snapshot
showing no remaining lock wait for the drill backend.

## Impact

- No production impact: the drill used a synthetic advisory-lock key reserved
  for testing, on a local/CI PostgreSQL instance.
- No business rows were read or modified; advisory locks touch no table data.
- Consumer experience: none. The exercise exists to prove the detection and
  recovery path works before a real lock incident needs it.

## Timeline (all times local, 2026-09-09)

| Time | Event |
| --- | --- |
| T+0s | Blocker connection opened, backend PID recorded, advisory lock acquired (`pg_advisory_lock` with the project test key) |
| T+0s | Waiter connection opened, PID recorded, same lock requested — blocked |
| T+1s | Diagnostics snapshot after the long-running threshold: waiter visible with `wait_event_type = Lock`, blocker PID mapped via `pg_blocking_pids` |
| T+1s | CONTAIN/RECOVER: only the drill's own advisory lock released (`pg_advisory_unlock`) |
| T+1s | Waiter acquired the lock and finished without error |
| T+2s | VERIFY: fresh diagnostics snapshot — drill PID no longer listed as blocked or blocking |
| T+2s | Cleanup: all drill connections closed in `finally`; no lock left held |

## Root cause

Not applicable in the production sense — the contention was deliberately
injected. The system property under test: PostgreSQL advisory locks are
session-scoped and invisible in table-level lock views, so a stuck lock is
diagnosable only through `pg_locks` / `pg_blocking_pids` correlation, which
the diagnostics module implements. The drill exists because an earlier design
assumption ("lock waits will be obvious in logs") was false: without explicit
blocking-PID mapping, a hung pipeline task shows only as a long-running
session.

## What went well

- Detection path worked end to end: the read-only diagnostics snapshot
  identified both the waiting session and the blocker PID.
- Containment was surgical: only the drill's own lock was released; no other
  session was cancelled or terminated.
- Verification distinguished real recovery (waiter completed, fresh snapshot
  clean) from a mere absence of errors.
- Cleanup was exception-safe: `finally` released state even on assertion
  failure.

## What went poorly / gaps

- Detection required a direct diagnostics call; no alert fires automatically
  on lock waits. A real lock incident would currently surface only as a
  `slow_pipeline` warning after the 180-second threshold.
- The drill covers advisory locks, not table-level row locks from real
  ingestion writes; contention between `bulk_load_source` batches is untested.
- Alert-to-incident mapping was not exercised: the drill bypassed
  `audit.pipeline_alerts` entirely.

## Action items

| # | Action | Owner | Due | Verification |
| --- | --- | --- | --- | --- |
| 1 | Add a diagnostics-based lock-wait check to the monitoring task so long lock waits raise an alert instead of only slowing the run | Data engineering | Next iteration | Unit test: monitoring snapshot with a lock-waiting session produces a warning alert row |
| 2 | Extend failure drills to a table-level row-lock scenario between two ingestion transactions | Data engineering | Next iteration | New drill test passes with the same INJECT→VERIFY lifecycle |
| 3 | Document `pg_blocking_pids` correlation in the operations runbook index | Data engineering | Done | This file + `failure_injection_runbook.md` |

## Lessons learned

- Advisory locks are a safe, reversible injection mechanism for practicing
  lock incidents without touching business data.
- "The pipeline is slow" and "the pipeline is blocked on a lock" look
  identical from task state alone; diagnostics must inspect wait events.
- Recovery evidence must include a post-recovery snapshot, not just the
  unblocked operation completing.

## References

- `docs/runbooks/failure_injection_runbook.md` — advisory-lock drill steps
- `src/ecommerce_pipeline/reliability/postgres_diagnostics.py` — detection layer
- `docs/runbooks/incident_response_runbook.md` — severity and lifecycle model
