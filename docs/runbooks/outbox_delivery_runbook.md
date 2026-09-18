# Transactional Outbox / Delivery Guarantee Runbook

Lab module: `src/ecommerce_pipeline/reliability/outbox_lab.py` (PART 20.6)
Drill: `tests/failure/test_transactional_outbox_drill.py`
Fake consumer: `tests/reliability/fake_invoice_api.py`

## 1. The problem: dual-write

A common integration looks like this:

1. `INSERT INTO orders ...` and `COMMIT` the business change.
2. Send an event to an external system (invoice API, message broker, webhook).

These are TWO separate systems with TWO separate commits, and neither ordering
is safe:

- **DB first, then send**: if the process crashes, the network drops, or the
  API returns 500 between step 1 and step 2, the business change is committed
  but the event is lost forever. The external system silently diverges.
- **Send first, then DB**: if the send succeeds but the database commit fails
  (constraint violation, deadlock, crash), the external system saw an event
  for a change that never happened. Equally unrecoverable.

There is no distributed transaction across "our PostgreSQL" and "their HTTP
API", so any code that does both in line has a dual-write gap.

## 2. The fix: transactional outbox

Instead of calling the external system inside the business transaction, write
the event to an **outbox table in the same database, in the same transaction**:

```text
BEGIN;
  INSERT INTO drill_lab.business_records (...);   -- the business change
  INSERT INTO drill_lab.outbox_events   (...);    -- the event, status=pending
COMMIT;                                           -- atomic: both or neither
```

`publish_business_event()` implements exactly this. Because both rows commit
atomically, it is *impossible* to persist the business change without its
event. A separate relay worker then:

1. Fetches pending events with `SELECT ... FOR UPDATE SKIP LOCKED`
   (`fetch_pending_events`) — SKIP LOCKED lets several worker processes poll
   the same outbox without blocking each other or double-processing rows.
2. Delivers each event over HTTP with an `Idempotency-Key` header
   (`deliver_event`).
3. Marks the event `delivered` or `failed` (`mark_delivered` / `mark_failed`),
   incrementing `attempts` either way. Events are never deleted on failure;
   `requeue_failed_event` moves them back to `pending` for the next round.

This mirrors the production alert-outbox concept in
`database/schema/10_create_pipeline_monitoring.sql` (PART 11): the database is
the durable hand-off point between the transaction and the unreliable network.

## 3. Why the consumer MUST be idempotent

The outbox gives **at-least-once** delivery, not exactly-once. Consider the
failure window in step 2–3 above: the API receives the event, creates the
invoice, but the HTTP response is lost (timeout, worker crash before
`mark_delivered` commits). From the worker's perspective delivery failed, so
the event is retried — and the API sees the same event twice.

Exactly-once *delivery* over an unreliable network is impossible (Two Generals
problem); what is achievable is **effectively-once processing**:

`at-least-once delivery + idempotent consumer = exactly-once effect`

The consumer makes this concrete by keying deduplication on the
`Idempotency-Key` header: the first request with a key creates the resource;
every retry with the same key returns the original result without creating a
duplicate. The fake invoice API (`tests/reliability/fake_invoice_api.py`)
implements exactly this contract, so the drill can *prove* that duplicate
deliveries produce exactly one invoice.

## 4. Drill lifecycle

`tests/failure/test_transactional_outbox_drill.py` runs against a real
PostgreSQL (same `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` /
`POSTGRES_USER` / `POSTGRES_PASSWORD` env vars as the other failure drills):

1. **Atomicity** — publish 3 events; assert business records and outbox events
   appear together in matching counts, all `pending`, `attempts = 0`.
2. **Network failure** — run the worker against a closed loopback port; assert
   every event survives as `failed` with `attempts = 1` and nothing is lost.
3. **Worker restart / recovery** — requeue the failed events, run a fresh
   worker round against the live fake API; assert all reach `delivered` with
   `attempts = 2` and `delivered_at` set.
4. **Duplicate delivery** — re-deliver an already delivered event (simulating
   a lost response + retry); assert the API still holds exactly one invoice
   per idempotency key.
5. **Verify** — every event is `delivered` and
   `invoice count == unique idempotency keys == published events`.

A second drill (`test_transient_api_failure_is_retried_exactly_once`) uses the
fake API's `?mode=fail_once` mode (HTTP 500 on the first attempt per key) to
show a transient server-side failure being retried to a single invoice.

## 5. Safety boundary

- The lab creates objects **only** in the `drill_lab` schema
  (`drill_lab.business_records`, `drill_lab.outbox_events`). No production
  schema (`raw`, `staging`, `mart`, `audit`, `public`) is ever referenced.
- `create_lab_schema` is idempotent (`IF NOT EXISTS`); re-running it is safe.
- Every drill drops the schema in a `finally` block via `drop_lab_schema`
  (`DROP SCHEMA IF EXISTS drill_lab CASCADE`), so a failed drill leaves no
  lab objects behind.
- The injected "network failure" only targets a closed loopback port; nothing
  on the real PostgreSQL instance is terminated or modified.
- No credentials are hardcoded; the drill uses the same environment-variable
  pattern as the other failure-injection drills.

## 6. Operational notes (if this were production)

- Poll the outbox frequently with small batches; `SKIP LOCKED` makes it safe
  to scale workers horizontally.
- Alert on outbox depth/age: `pending` or `failed` rows older than a threshold
  mean the consumer or the network is down, but no data is lost.
- Cap retries with backoff; park repeatedly failing events for investigation
  instead of hot-looping them.
- Keep the idempotency key stable for the lifetime of an event — derive it
  from the event identity (`event_type:event_id`), never regenerate per retry.
