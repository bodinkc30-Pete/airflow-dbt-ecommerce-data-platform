"""Failure-injection drill: transactional outbox delivery guarantee (PART 20.6).

Uses a REAL PostgreSQL database (env-var connection, same as the other drills)
and a fake invoice API running on a localhost thread.

Safety boundary:
- All lab objects live in the ``drill_lab`` schema only; production schemas
  are never touched.
- The schema is dropped in ``finally`` even if an assertion fails.
- The injected "network failure" only points the worker at a closed loopback
  port; nothing on the real PostgreSQL instance is terminated or modified.

Drill scenarios:
1. Atomicity    - business record + outbox event commit in ONE transaction.
2. Network down - worker cannot reach the API; events stay retryable, none lost.
3. Worker retry - after the API is back, a new worker round delivers them.
4. Duplicates   - re-delivering the same event does NOT create a second invoice
                  (idempotent consumer keyed by Idempotency-Key).
5. Verify       - every event delivered; invoice count == unique event count.
"""

import os

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.reliability.outbox_lab import (
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_PENDING,
    count_business_records,
    create_lab_schema,
    default_http_post,
    deliver_event,
    drop_lab_schema,
    fetch_pending_events,
    list_outbox_events,
    publish_business_event,
    requeue_failed_event,
    run_outbox_worker,
)
from tests.reliability.fake_invoice_api import FakeInvoiceApi

CLOSED_PORT = 59999
DEAD_API_URL = f"http://127.0.0.1:{CLOSED_PORT}"


def _connect():
    return connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )


def _fail_once_post(url, *, json_body, headers, timeout_seconds):
    """Route the delivery through the fake API's transient-failure mode."""
    return default_http_post(
        f"{url}?mode=fail_once",
        json_body=json_body,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )


def test_transactional_outbox_end_to_end_drill() -> None:
    connection = _connect()
    api = FakeInvoiceApi().start()
    try:
        # Clean slate in case a previous drill run was interrupted.
        drop_lab_schema(connection)
        create_lab_schema(connection)

        # --- Scenario 1: atomicity -------------------------------------
        # Business change + outbox event are written in ONE transaction, so
        # the two tables can never disagree (no dual-write gap).
        event_ids = [
            publish_business_event(
                connection,
                note=f"drill order #{index}",
                event_type="order_created",
                payload={"order_number": index, "amount": 100 * index},
            )
            for index in range(1, 4)
        ]
        assert count_business_records(connection) == 3
        events = list_outbox_events(connection)
        assert len(events) == 3
        assert {event.event_id for event in events} == set(event_ids)
        assert all(event.status == STATUS_PENDING for event in events)
        assert all(event.attempts == 0 for event in events)
        assert all(event.delivered_at is None for event in events)

        # --- Scenario 2: network failure -------------------------------
        # The invoice API is unreachable (closed port). The worker round must
        # NOT lose events: they stay in the outbox, marked failed, attempts=1.
        failed_round = run_outbox_worker(
            connection,
            api_base_url=DEAD_API_URL,
            max_events=10,
            timeout_seconds=2.0,
        )
        assert failed_round.fetched == 3
        assert failed_round.delivered == 0
        assert failed_round.failed == 3
        assert all(result.error for result in failed_round.results)
        assert api.request_count == 0

        stuck_events = list_outbox_events(connection)
        assert all(event.status == STATUS_FAILED for event in stuck_events)
        assert all(event.attempts == 1 for event in stuck_events)
        assert count_business_records(connection) == 3  # nothing was lost

        # --- Scenario 3: worker restart / recovery ---------------------
        # A retry policy requeues failed events; the next worker round (e.g.
        # after a worker restart, once the API is back) delivers them.
        for event in stuck_events:
            requeue_failed_event(connection, event.event_id)
        pending = fetch_pending_events(connection, limit=10)
        connection.commit()  # release the SKIP LOCKED row locks
        assert {event.event_id for event in pending} == set(event_ids)

        recovered_round = run_outbox_worker(
            connection,
            api_base_url=api.base_url,
            max_events=10,
        )
        assert recovered_round.fetched == 3
        assert recovered_round.delivered == 3
        assert recovered_round.failed == 0

        delivered_events = list_outbox_events(connection)
        assert all(event.status == STATUS_DELIVERED for event in delivered_events)
        assert all(event.attempts == 2 for event in delivered_events)
        assert all(event.delivered_at is not None for event in delivered_events)
        assert len(api.invoices) == 3

        # --- Scenario 4: duplicate delivery ----------------------------
        # Simulate a lost response: the worker re-delivers an already
        # delivered event. The idempotent consumer must NOT create a second
        # invoice for the same Idempotency-Key.
        replayed = delivered_events[0]
        for _ in range(2):
            replay = deliver_event(event=replayed, api_base_url=api.base_url)
            assert replay.success
        assert api.request_count == 3 + 2
        assert len(api.invoices) == 3  # still exactly one invoice per event
        replayed_keys = [request.idempotency_key for request in api.requests]
        # Once from the scenario-3 recovery delivery + twice from the replays.
        assert replayed_keys.count(replayed.idempotency_key) == 3

        # --- Scenario 5: final verification ----------------------------
        final_events = list_outbox_events(connection)
        assert all(event.status == STATUS_DELIVERED for event in final_events)
        unique_keys = {event.idempotency_key for event in final_events}
        assert len(api.invoices) == len(unique_keys) == len(event_ids)
        assert count_business_records(connection) == len(event_ids)
    finally:
        try:
            drop_lab_schema(connection)
        finally:
            connection.close()
            api.stop()


def test_transient_api_failure_is_retried_exactly_once() -> None:
    """A 500 on the first attempt must not create a duplicate invoice."""
    connection = _connect()
    api = FakeInvoiceApi().start()
    try:
        drop_lab_schema(connection)
        create_lab_schema(connection)

        event_id = publish_business_event(
            connection,
            note="drill order #transient",
            event_type="order_created",
            payload={"order_number": 99, "amount": 42},
        )

        # Round 1: the API fails the first request per key with HTTP 500.
        first_round = run_outbox_worker(
            connection,
            api_base_url=api.base_url,
            max_events=5,
            http_post_func=_fail_once_post,
        )
        assert first_round.delivered == 0
        assert first_round.failed == 1
        assert first_round.results[0].status_code == 500
        (failed_event,) = list_outbox_events(connection)
        assert failed_event.status == STATUS_FAILED
        assert failed_event.attempts == 1
        assert api.invoices == []  # the 500 created nothing

        # Round 2: retry the same event against the recovered API.
        requeue_failed_event(connection, event_id)
        second_round = run_outbox_worker(
            connection,
            api_base_url=api.base_url,
            max_events=5,
        )
        assert second_round.delivered == 1
        assert second_round.failed == 0

        (final_event,) = list_outbox_events(connection)
        assert final_event.status == STATUS_DELIVERED
        assert final_event.attempts == 2

        # The API saw two requests with one idempotency key -> one invoice.
        assert api.request_count == 2
        assert len(api.invoices) == 1
        assert api.invoices[0]["idempotency_key"] == final_event.idempotency_key
    finally:
        try:
            drop_lab_schema(connection)
        finally:
            connection.close()
            api.stop()
