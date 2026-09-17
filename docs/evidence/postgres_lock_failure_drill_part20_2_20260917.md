# PART 20.2A โ€” PostgreSQL Lock Failure Drill Evidence

Date: 2026-09-17 (Asia/Bangkok)

## Scope

This drill validates the existing PostgreSQL diagnostics layer under an active,
controlled lock incident. It does not modify business tables, ingestion contracts,
Airflow task behavior, dbt model grain, or transaction ownership.

## Injection method

Two dedicated PostgreSQL sessions request the same synthetic advisory lock. The
first session holds the lock; the second waits. A separate read-only diagnostics
connection observes the incident.

The drill verifies:

- blocked PID -> blocker PID detection;
- connection waiting count;
- `wait_event_type = Lock` after the long-running threshold;
- controlled release of only the injected advisory lock;
- completion of the waiting operation; and
- absence of the blocking relationship after recovery.

## Failure-driven test correction

The first drill run detected the blocking relationship correctly but failed an
assertion that expected the waiter to already qualify as long-running. Evidence
showed the blocker was detected in under one second while the configured
long-running threshold was one second.

The test was corrected to separate immediate blocker detection from the aged
long-running observation. No production diagnostics code was changed.

## Observed validation

- First run: FAIL on the premature long-running timing assumption.
- Corrected live drill: `1 passed in 7.28s`.
- CI contract plus live drill: `13 passed in 7.30s`.
- Post-drill advisory lock check: `0 rows`.
- PostgreSQL integration + failure suite: `34 passed in 80.42s`.
- Service-free Quality Gate regression: `369 passed in 1.55s`.
- CI routing now keeps `tests/failure` out of the service-free Quality Gate and
  runs it with the PostgreSQL integration job.

## Acceptance boundary

This proves one controlled PostgreSQL lock scenario only. PART 20.2 remains open
for additional failure classes such as dependency unavailability, timeout, and
recovery drills; those must be added from observed contracts rather than simulated
claims.
