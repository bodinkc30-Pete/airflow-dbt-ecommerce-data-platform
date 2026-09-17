# Postmortem — PostgreSQL Lock Contention Drill (2026-09)

> Scope note: this postmortem documents a **controlled failure-injection
> drill** run on 2026-09-17 against local/CI PostgreSQL, not a production
> outage. No business data, users, or stakeholders were affected. All
> quantitative claims below come from recorded drill and test evidence; where
> the evidence has no absolute clock timestamps, relative offsets are used and
> labelled as such. Primary evidence:
> [PART 20.2A drill evidence](../evidence/postgres_lock_failure_drill_part20_2_20260917.md)
> and the drill test
> [tests/failure/test_postgres_lock_incident.py](../../tests/failure/test_postgres_lock_incident.py).

## Summary

A controlled PostgreSQL lock incident was injected to prove that the existing
read-only diagnostics layer detects lock contention: one session held a
synthetic advisory lock (project-reserved test key `62020001`) while a second
session waited on it, and a third read-only session observed the database. The
diagnostics layer detected the blocked-PID to blocker-PID relationship and the
aged `wait_event_type = Lock` waiter as designed, and the waiting operation
completed after a controlled release. The first drill run failed — not because
detection failed, but because the test asserted the waiter was "long-running"
before the one-second threshold had elapsed. The test was corrected; no
production diagnostics code was changed.

## Impact

None on production or business data. The drill ran against local/CI PostgreSQL
with synthetic advisory locks only, per the safety boundary in the
[Failure Injection Runbook](../runbooks/failure_injection_runbook.md): no
business tables were modified, no arbitrary sessions were terminated, and all
injected state was released in `finally` cleanup. The only real cost was one
failed first drill run caused by a test-design defect, which consumed one
diagnose-fix-rerun cycle.

Had this same mechanism (a held lock blocking a pipeline session) occurred in
production against pipeline tables, impact would have been delayed or blocked
ingestion/transformation tasks — a SEV2-class event under the
[Incident Response Runbook](../runbooks/incident_response_runbook.md).

## Severity

SEV4 — controlled investigation/drill with no user impact. Severity stayed at
SEV4 throughout; the only unexpected event was a failing test assertion, not a
detection or recovery failure.

## Timeline

Absolute clock times were not recorded during the drill; offsets below are
reconstructed from the test flow and recorded durations in the drill evidence
(corrected live drill: `1 passed in 7.28s`), all on 2026-09-17 (Asia/Bangkok).

| Time | Event |
| --- | --- |
| T+0 | Blocker connection acquired advisory lock key `62020001`; blocker PID recorded |
| T+0 | Waiter thread requested the same advisory lock; waiter PID recorded |
| < T+1s | Read-only diagnostics snapshot detected the blocked-PID → blocker-PID relationship; `connections.waiting >= 1` confirmed |
| T+1.1s | Aged snapshot confirmed the waiter in `wait_event_type = Lock` past the 1-second long-running threshold |
| After detection | Blocker released only the drill's advisory lock via `pg_advisory_unlock` |
| Within 5s of release | Waiter completed lock/unlock with no error |
| Post-recovery | Fresh snapshot showed no blocking relationship for the waiter PID; post-drill advisory lock check returned `0 rows` |

First drill run (earlier the same day): detected the blocking relationship
correctly, then FAILED on the premature long-running assertion.

## Detection

Detection worked exactly as designed and was entirely automated: the
diagnostics connection polled `load_postgres_diagnostics()` from
`src/ecommerce_pipeline/reliability/postgres_diagnostics.py` (1-second
long-running threshold, top-5 query limit) until the blocking relationship
appeared. Blocking was detected in under one second — faster than the
configured long-running threshold. This validates that a real lock incident
would be caught by the diagnostics layer that powers
`scripts/diagnose_postgres.py` without waiting for a human to notice a stalled
pipeline.

## Root Cause

Two distinct causes, kept separate:

1. **The injected incident (intended):** a synthetic PostgreSQL advisory lock
   (`pg_advisory_lock(62020001)`) held by a dedicated blocker session while a
   waiter session requested the same key. Root-cause category for the
   simulated condition: `database`.
2. **The first-run failure (unintended, the real defect):** a test-design
   error. The initial assertion expected the waiter to already qualify as
   long-running immediately after blocker detection, but detection completed
   in under one second while the long-running threshold was one second. The
   observation was simply taken before the waiter had aged past the
   threshold. No production code defect was found.

## Contributing Factors

- Immediate detection and a 1-second ageing threshold sit on the same order of
  magnitude, so a single combined assertion was racy by construction.
- The drill had no prior run, so the timing relationship between detection
  latency and the threshold had never been observed before the first run.
- No environment or parity gap contributed: the failure reproduced purely from
  assertion timing.

## Mitigation

For the injected incident, mitigation was the drill's controlled containment:
the blocker released only the advisory lock it created
(`pg_advisory_unlock(62020001)`), with `pg_advisory_unlock_all()` on the
drill's own session as `finally` cleanup. No other session was cancelled,
terminated, or altered — matching the runbook rule that drills never touch
sessions they do not own.

For the first-run failure, mitigation was to stop rerunning and fix the test
contract before further drill attempts, per the escalation rule against
stacking failure injections on an unresolved synthetic incident.

## Recovery

The waiter operation (`pg_advisory_lock` followed by `pg_advisory_unlock`)
completed within the 5-second completion window after release, with no error.
The drill test was corrected to separate **immediate blocker detection** from
the **aged long-running observation**, and the corrected live drill passed:
`1 passed in 7.28s`. All drill connections were closed in `finally` cleanup.

## Verification

Verification went beyond "the retry passed":

- Post-recovery snapshot contained no blocking relationship for the waiter PID.
- Post-drill advisory lock check returned `0 rows` — no injected residue.
- CI contract plus live drill: `13 passed in 7.30s`.
- PostgreSQL integration + failure suite: `34 passed in 80.42s`.
- Service-free Quality Gate regression: `369 passed in 1.55s`.

## Why Monitoring Did or Did Not Catch It

Detection caught the injected incident, and it caught it *before* the ageing
threshold — the blocking relationship was visible in under one second. The
first-run failure was not a monitoring miss; it was the test asserting a
threshold-aged signal earlier than the threshold allowed. The genuine gap this
exposed is procedural: drill assertions must distinguish "detected now" from
"aged past threshold", because conflating them produces false failures that
erode trust in drills.

## Corrective Actions

| Action | Owner | Due date |
| --- | --- | --- |
| Split drill assertions into immediate blocker detection vs aged long-running observation | Data engineering | Done 2026-09-17 |
| Route `tests/failure` out of the service-free Quality Gate and into the PostgreSQL integration job so drills always run against a live database | Data engineering | Done 2026-09-17 |
| Add remaining PART 20.2 failure classes (dependency unavailability, timeout, recovery drills) from observed contracts | Data engineering | Open — next drill cycle |

## Regression Prevention

The corrected drill itself is the regression guard:
`tests/failure/test_postgres_lock_incident.py` now permanently re-verifies
blocked-PID → blocker-PID detection, `wait_event_type = Lock` ageing,
controlled release, waiter completion, and post-recovery cleanliness on every
PostgreSQL integration run. CI routing keeps the failure suite attached to the
PostgreSQL integration job so the drill cannot be silently skipped in
environments without a database.

## Lessons Learned

**What went well:** detection was fast (sub-second), containment was surgical
(only the drill's own lock was released), cleanup was complete (`0` residual
advisory locks), and the failure-driven correction touched only test code —
the production diagnostics layer was validated unchanged.

**What was lucky / needs attention:** the first run's failure was luck in
disguise — it surfaced a racy assertion before anyone relied on it during a
real incident. The lesson generalizes: in failure drills, always separate
detection-time assertions from threshold-aged assertions, and treat any drill
failure as a signal about the drill contract first, not as permission to patch
production code. This is the same discipline the
[Reliability Incident Runbook](../runbooks/reliability_incident_runbook.md)
applies to real PostgreSQL deadlock recovery: classify from evidence, recover
with the narrowest safe action, and verify before resolving.
