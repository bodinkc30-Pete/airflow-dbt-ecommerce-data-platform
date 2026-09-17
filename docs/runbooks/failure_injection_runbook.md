# Failure Injection Runbook

## Purpose

Use controlled synthetic incidents to verify detection, diagnosis, recovery, and
post-recovery validation without touching private business data or changing the
closed production-oriented architecture.

## Safety boundary

- Run drills only against local/CI PostgreSQL, never an unknown production host.
- Prefer reversible mechanisms such as PostgreSQL advisory locks.
- Do not terminate arbitrary sessions automatically.
- Do not modify business rows merely to create an incident.
- The test process owns only the synthetic resources it creates.
- Always release injected state in `finally` cleanup.

## Drill lifecycle

```text
INJECT -> DETECT -> DIAGNOSE -> CONTAIN
-> RECOVER -> VERIFY -> CAPTURE EVIDENCE
```

A passing retry or reconnect alone is not recovery evidence. Verify that the
blocking/failure condition is gone and the affected operation can finish.

## PostgreSQL advisory-lock drill

1. Open a dedicated blocker connection and record its backend PID.
2. Acquire a synthetic advisory lock using a project-reserved test key.
3. Open a second connection, record its PID, and request the same lock.
4. Use the read-only PostgreSQL diagnostics layer to detect the blocker mapping.
5. After the configured long-running threshold, verify `wait_event_type = Lock`.
6. Release only the advisory lock created by the drill.
7. Verify the waiting operation finishes without error.
8. Capture a fresh diagnostics snapshot and confirm the waiter is no longer blocked.
9. Close all drill connections even when an assertion fails.

## PostgreSQL long-running transaction drill

1. Open a dedicated connection and record its backend PID.
2. Begin a transaction (implicit via psycopg2) and run a trivial `SELECT 1`;
   hold the transaction open past the long-running threshold.
3. Detect the aged transaction in the diagnostics snapshot as
   `state = idle in transaction`.
4. Recover with `ROLLBACK` of the drill's own transaction only.
5. Capture a fresh snapshot and confirm the PID is gone.
6. Roll back and close all drill connections in `finally`.

## PostgreSQL slow query drill

1. Open a dedicated connection, record its backend PID, and run
   `SELECT pg_sleep(...)` in a background thread.
2. Detect the sleeping session as a long-running `active` query.
3. Contain by calling `pg_cancel_backend` with the drill's own PID only;
   never cancel or terminate any other session.
4. Confirm the thread observes `QueryCanceled` and finishes.
5. Roll back the drill's own cancelled session: cancellation leaves it in
   `idle in transaction`, which still counts as a long-running session and
   would fail verification.
6. Capture a fresh snapshot and confirm the PID is gone.
7. If the drill fails before containment, cancel only the drill's PID in
   `finally` and close all connections.

## PostgreSQL connection failure and recovery drill

1. Attempt to connect to a closed localhost port and assert
   `psycopg2.OperationalError` is raised.
2. Recover by connecting to the real PostgreSQL via the standard env-var
   helper and run `SELECT 1`.
3. Verify with a full diagnostics snapshot to prove the pipeline is usable
   again after the failure.

## Raw-layer bad data rejection drill

1. Count rows in `raw.orders` before the drill.
2. Attempt to insert a synthetic row with a whitespace-only `order_id`;
   supply plausible values for all other `NOT NULL` columns.
3. Assert the insert is rejected with a `CheckViolation`
   (`chk_raw_orders_order_id_not_blank`); never disable constraints to force
   the insert through.
4. Recover with `ROLLBACK`; the drill never commits.
5. Verify the row count is unchanged so no bad row leaked into the raw layer.

## Alert delivery failure drill (unit, no PostgreSQL required)

1. Send a webhook alert to an https URL with nothing listening and assert the
   result is `status = failed` with an error, without raising.
2. Send alerts to non-https URLs (`http://`, `file://`) and assert the scheme
   guard rejects them with `status = failed`.
3. Send an alert with no webhook URL configured and assert
   `status = not_configured`.
4. In all scenarios the alert is still recorded locally; delivery failure must
   never crash the pipeline.

## Escalation rule

If the drill cannot clean itself up, stop and inspect PostgreSQL state before
running another scenario. Never stack additional failure injections on top of an
unresolved synthetic incident.
