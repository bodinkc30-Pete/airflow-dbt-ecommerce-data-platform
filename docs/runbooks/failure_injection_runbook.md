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

## Escalation rule

If the drill cannot clean itself up, stop and inspect PostgreSQL state before
running another scenario. Never stack additional failure injections on top of an
unresolved synthetic incident.
