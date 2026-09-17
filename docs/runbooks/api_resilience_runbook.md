# API Resilience Runbook (PART 20.5 — External API Resilience Lab)

## Purpose

This lab demonstrates how to integrate with an **unreliable external HTTP API** safely,
using a synthetic localhost server instead of a real third party. It is intentionally
**not wired into any pipeline** — it exists to exercise and document production
integration patterns in isolation:

| Pattern | Why it exists |
| --- | --- |
| Per-attempt timeout | A hung connection must not block a worker forever. |
| Retry with exponential backoff + jitter | Transient faults (timeouts, connection errors, HTTP 429/5xx) usually clear; backoff avoids hammering a struggling server, jitter decorrelates retries across many clients. |
| Retry classification | Only *transient* errors are retried. HTTP 4xx (except 429) means the request itself is wrong — retrying it just wastes budget. |
| Retry budget | Caps the number of retries per time window so retries cannot amplify an outage (retry storm). |
| Circuit breaker | After N consecutive failures, stop calling the dependency entirely for a cooldown, then probe with a single half-open request. |
| Idempotency key | Makes retries *safe* for non-idempotent operations (e.g. POST create-invoice). |

## Files

- `src/ecommerce_pipeline/reliability/api_resilience.py` — `ResilientApiClient`,
  `CallResult`, `CallStatus`, `CircuitBreakerState`.
- `tests/reliability/fake_api_server.py` — `FakeApiServer`, a threaded localhost
  HTTP server with scripted failure scenarios.
- `tests/reliability/test_api_resilience.py` — the executable lab.

## Why retry must be paired with idempotency

Consider `POST /invoices`:

1. The server **receives** the request and creates the invoice.
2. The response is **lost** (proxy timeout, connection reset on the way back).
3. The client sees a timeout and cannot distinguish "server never got it" from
   "server did it but the reply vanished".
4. A naive retry **creates a second invoice** — a duplicate financial record.

With an `Idempotency-Key` header, the client generates one key per *logical*
request and reuses it across every retry. The server deduplicates on the key:
the first delivery creates the invoice, replays return the original result.
The lab's `/lost-response` endpoint simulates exactly this: the server records
the invoice, then answers slower than the client timeout. The test fires the
same key twice and asserts the server still holds exactly **one** invoice.

Rule of thumb: **retry only when the operation is idempotent, or make it
idempotent with a key first.**

## Retry budget

Backoffs slow retries down but do not cap their *volume*. If every task in a
backfill retries 5 times while the downstream API is degraded, you multiply the
load exactly when it can least afford it (retry storm). The client tracks
retry timestamps in a sliding window; once `retry_budget_per_window` retries
have been spent inside `retry_budget_window_seconds`, further calls **fail
fast** with a `retry budget exhausted` error instead of sending more traffic.
Retries are budgeted, first attempts are not — new work may still proceed while
retries are throttled.

## Circuit breaker

State machine around each dependency:

- **closed** — normal operation; failures are counted.
- **open** — after `circuit_failure_threshold` consecutive failed calls, every
  call is rejected immediately (`rejected_by_breaker`, zero HTTP traffic) for
  `circuit_reset_seconds`. This gives the dependency room to recover and keeps
  local workers from blocking on timeouts.
- **half-open** — after the reset window, exactly one probe call is allowed.
  Success closes the breaker; failure re-opens it for another window.

## Running the lab

```bash
# from the repository root
pip install pytest
PYTHONPATH=src pytest tests/reliability/test_api_resilience.py -v
```

All tests run against a random localhost port; no external network, database,
or Docker service is required. The whole file completes in a few seconds
(client timeouts are 0.3 s, backoff base is 0.01 s).

### Scenarios exposed by the fake server

| Path | Behavior |
| --- | --- |
| `/ok` | 200 `{"status": "created"}`; records the Idempotency-Key. |
| `/timeout` | Sleeps 30 s before responding — always exceeds the test client timeout. |
| `/rate-limited` | Always 429. |
| `/server-error` | Always 500. |
| `/flaky?fail_times=N` | 500 for the first N requests with a given Idempotency-Key, then 200. |
| `/lost-response` | Creates an invoice deduplicated by Idempotency-Key, then responds too slowly — simulates a lost response. |

Server-side observations (request counts per path, keys seen, invoices created)
are exposed via `server.state` for assertions.

## Applying the pattern to a real integration

1. Wrap the third-party call in `ResilientApiClient` (or port the same policy
   onto `requests`/`httpx` if the dependency is available). Configure:
   - `timeout_seconds` — slightly above the dependency's p99 latency.
   - `max_attempts` — 3–5 for interactive paths, lower for batch.
   - `backoff_base_seconds` / `backoff_multiplier` / `jitter=True` in production.
   - `retry_budget_per_window` — derived from how much extra load the
     dependency can absorb (e.g. +10% of expected RPS).
   - `circuit_failure_threshold` / `circuit_reset_seconds` — how fast to give
     up and how long to wait before probing.
2. Always send a stable `Idempotency-Key` per logical operation (e.g. derived
   from the business key: `order_id + operation`), and verify the provider
   actually deduplicates on it. If it does not, buffer and reconcile instead
   of blind retrying.
3. Treat `CallResult.status` as data: alert on `rejected_by_breaker` (the
   dependency is down) and on budget exhaustion (retry amplification).
4. Keep 4xx failures loud — they signal a contract bug, not a transient fault.

## Tuning notes / failure modes to watch

- **Breaker flapping**: reset window shorter than the dependency's real
  recovery time. Increase `circuit_reset_seconds`.
- **Budget too tight**: legitimate retries rejected during short blips.
  Widen the window or raise the limit.
- **Retryable error misclassification**: some APIs return 400/409 for
  retryable conditions (e.g. optimistic-lock conflicts). Classify by the
  provider's error *body*, not just the status code, in real integrations.
- **Idempotency-Key reuse across logical requests**: keys must be unique per
  logical operation; reusing one across *different* operations silently drops
  real work on an idempotent server.
