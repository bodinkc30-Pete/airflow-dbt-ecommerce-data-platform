"""Unit tests for the transactional outbox lab (no PostgreSQL required).

Uses a recording fake connection to verify SQL generation/safety (everything
scoped to the ``drill_lab`` schema), state-transition rules, delivery header
behaviour, and worker bookkeeping.
"""

import urllib.error
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from ecommerce_pipeline.reliability import outbox_lab
from ecommerce_pipeline.reliability.outbox_lab import (
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_PENDING,
    OutboxEvent,
    build_idempotency_key,
    create_lab_schema,
    deliver_event,
    drop_lab_schema,
    fetch_pending_events,
    list_outbox_events,
    mark_delivered,
    mark_failed,
    publish_business_event,
    requeue_failed_event,
    resolve_next_status,
    run_outbox_worker,
)


class FakeCursor:
    """Minimal cursor double that records SQL and serves scripted results."""

    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self._connection.executed.append((sql, params))
        if self._connection.fail_on_execute_number == len(self._connection.executed):
            raise RuntimeError("injected execution failure")

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._connection.fetchall_result

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._connection.fetchone_result


class FakeConnection:
    """Minimal connection double recording executed SQL and txn boundaries."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []
        self.fetchall_result: list[tuple[Any, ...]] = []
        self.fetchone_result: tuple[Any, ...] | None = None
        self.commits = 0
        self.rollbacks = 0
        self.fail_on_execute_number: int | None = None

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _sample_event(
    *,
    status: str = STATUS_PENDING,
    attempts: int = 0,
    event_type: str = "order_created",
) -> OutboxEvent:
    event_id = uuid4()
    return OutboxEvent(
        event_id=event_id,
        event_type=event_type,
        payload={"order_number": 1},
        idempotency_key=build_idempotency_key(event_type, event_id),
        status=status,
        attempts=attempts,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        delivered_at=None,
    )


def _event_row(event: OutboxEvent) -> tuple[Any, ...]:
    return (
        str(event.event_id),
        event.event_type,
        event.payload,
        event.idempotency_key,
        event.status,
        event.attempts,
        event.created_at,
        event.delivered_at,
    )


# --- Schema safety ---------------------------------------------------------


def test_create_lab_schema_is_idempotent_and_scoped_to_drill_lab() -> None:
    connection = FakeConnection()

    create_lab_schema(connection)  # type: ignore[arg-type]

    assert len(connection.executed) == 3
    ddl = "\n".join(sql for sql, _ in connection.executed)
    assert "CREATE SCHEMA IF NOT EXISTS drill_lab" in ddl
    assert ddl.count("CREATE TABLE IF NOT EXISTS drill_lab.") == 2
    assert "drill_lab.business_records" in ddl
    assert "drill_lab.outbox_events" in ddl
    # Safety: no production schema is referenced anywhere.
    for forbidden in ("raw.", "staging.", "mart.", "audit.", "public."):
        assert forbidden not in ddl
    # Idempotency key uniqueness + status guard live in the table definition.
    assert "idempotency_key TEXT NOT NULL UNIQUE" in ddl
    assert "'pending'" in ddl and "'delivered'" in ddl and "'failed'" in ddl
    assert connection.commits == 1


def test_drop_lab_schema_only_drops_drill_lab() -> None:
    connection = FakeConnection()

    drop_lab_schema(connection)  # type: ignore[arg-type]

    ((sql, _),) = connection.executed
    assert sql == "DROP SCHEMA IF EXISTS drill_lab CASCADE;"
    assert connection.commits == 1


def test_lab_schema_name_is_fixed() -> None:
    assert outbox_lab.LAB_SCHEMA == "drill_lab"
    for statement in (
        outbox_lab.INSERT_BUSINESS_SQL,
        outbox_lab.INSERT_OUTBOX_SQL,
        outbox_lab.FETCH_PENDING_SQL,
        outbox_lab.MARK_DELIVERED_SQL,
        outbox_lab.MARK_FAILED_SQL,
    ):
        assert "drill_lab." in statement


# --- Atomic publish --------------------------------------------------------


def test_publish_business_event_is_one_transaction() -> None:
    connection = FakeConnection()

    event_id = publish_business_event(  # type: ignore[arg-type]
        connection,
        note="order #1",
        event_type="order_created",
        payload={"amount": 10},
    )

    # Both INSERTs happen before the single commit -> atomic pair.
    assert len(connection.executed) == 2
    assert connection.commits == 1
    assert connection.rollbacks == 0
    business_sql, business_params = connection.executed[0]
    outbox_sql, outbox_params = connection.executed[1]
    assert "INSERT INTO drill_lab.business_records" in business_sql
    assert business_params == ("order #1",)
    assert "INSERT INTO drill_lab.outbox_events" in outbox_sql
    assert outbox_params is not None
    assert outbox_params[0] == str(event_id)
    assert outbox_params[1] == "order_created"
    assert outbox_params[3] == build_idempotency_key("order_created", event_id)


def test_publish_business_event_rolls_back_both_inserts_on_failure() -> None:
    connection = FakeConnection()
    connection.fail_on_execute_number = 2  # second INSERT blows up

    with pytest.raises(RuntimeError, match="injected execution failure"):
        publish_business_event(  # type: ignore[arg-type]
            connection,
            note="order #1",
            event_type="order_created",
            payload={},
        )

    assert connection.commits == 0
    assert connection.rollbacks == 1  # business record must NOT survive alone


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"note": "  ", "event_type": "order_created"}, "note"),
        ({"note": "x", "event_type": ""}, "event_type"),
    ],
)
def test_publish_business_event_validates_input(kwargs: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        publish_business_event(FakeConnection(), payload={}, **kwargs)  # type: ignore[arg-type]


# --- Fetch / state transitions ---------------------------------------------


def test_fetch_pending_events_uses_skip_locked() -> None:
    connection = FakeConnection()
    connection.fetchall_result = [_event_row(_sample_event())]

    events = fetch_pending_events(connection, limit=7)  # type: ignore[arg-type]

    ((sql, params),) = connection.executed
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "status = 'pending'" in sql
    assert params == (7,)
    assert len(events) == 1
    assert events[0].status == STATUS_PENDING


def test_fetch_pending_events_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="limit must be > 0"):
        fetch_pending_events(FakeConnection(), limit=0)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("current", "succeeded", "expected"),
    [
        (STATUS_PENDING, True, STATUS_DELIVERED),
        (STATUS_PENDING, False, STATUS_FAILED),
        (STATUS_FAILED, True, STATUS_DELIVERED),
        (STATUS_FAILED, False, STATUS_FAILED),
        (STATUS_DELIVERED, True, STATUS_DELIVERED),
        (STATUS_DELIVERED, False, STATUS_DELIVERED),  # terminal, idempotent
    ],
)
def test_resolve_next_status(current: str, succeeded: bool, expected: str) -> None:
    assert resolve_next_status(current_status=current, delivery_succeeded=succeeded) == expected


def test_resolve_next_status_rejects_unknown_status() -> None:
    with pytest.raises(ValueError, match="Unknown outbox event status"):
        resolve_next_status(current_status="archived", delivery_succeeded=True)


def test_build_idempotency_key_format_and_validation() -> None:
    event_id = uuid4()
    key = build_idempotency_key("order_created", event_id)
    assert key == f"order_created:{event_id}"
    with pytest.raises(ValueError, match="event_type"):
        build_idempotency_key(" ", event_id)


# --- Marking ---------------------------------------------------------------


def test_mark_delivered_increments_attempts_and_stamps_delivered_at() -> None:
    connection = FakeConnection()
    event_id = uuid4()

    mark_delivered(connection, event_id)  # type: ignore[arg-type]

    ((sql, params),) = connection.executed
    assert "status = 'delivered'" in sql
    assert "attempts = attempts + 1" in sql
    assert "delivered_at = CURRENT_TIMESTAMP" in sql
    assert params == (str(event_id),)
    assert connection.commits == 1


def test_mark_failed_increments_attempts_and_stays_retryable() -> None:
    connection = FakeConnection()
    event_id = uuid4()

    mark_failed(connection, event_id, "connection refused")  # type: ignore[arg-type]

    ((sql, params),) = connection.executed
    assert "status = 'failed'" in sql
    assert "attempts = attempts + 1" in sql
    assert "delivered_at" not in sql
    assert params == (str(event_id),)


def test_requeue_failed_event_only_touches_failed_rows() -> None:
    connection = FakeConnection()
    event_id = uuid4()

    requeue_failed_event(connection, event_id)  # type: ignore[arg-type]

    ((sql, params),) = connection.executed
    assert "SET status = 'pending'" in sql
    assert "status = 'failed'" in sql  # guard: delivered rows are never requeued
    assert params == (str(event_id),)


def test_list_outbox_events_maps_rows() -> None:
    connection = FakeConnection()
    event = _sample_event(status=STATUS_DELIVERED, attempts=2)
    connection.fetchall_result = [_event_row(event)]

    events = list_outbox_events(connection)  # type: ignore[arg-type]

    assert events == [event]


# --- Delivery --------------------------------------------------------------


def test_deliver_event_sends_idempotency_key_header() -> None:
    event = _sample_event()
    captured: dict[str, Any] = {}

    def fake_post(url: str, *, json_body, headers, timeout_seconds) -> int:
        captured.update(url=url, json_body=json_body, headers=headers, timeout=timeout_seconds)
        return 200

    result = deliver_event(
        event=event,
        api_base_url="http://127.0.0.1:9000/",
        http_post_func=fake_post,
    )

    assert result.success
    assert result.status_code == 200
    assert result.error is None
    assert captured["url"] == "http://127.0.0.1:9000/invoice"
    assert captured["headers"]["Idempotency-Key"] == event.idempotency_key
    assert captured["json_body"]["event_id"] == str(event.event_id)
    assert captured["json_body"]["event_type"] == event.event_type


def test_deliver_event_captures_http_500_without_raising() -> None:
    event = _sample_event()

    def failing_post(url: str, *, json_body, headers, timeout_seconds) -> int:
        raise urllib.error.HTTPError(url, 500, "Internal Server Error", None, None)

    result = deliver_event(
        event=event,
        api_base_url="http://127.0.0.1:9000",
        http_post_func=failing_post,
    )

    assert not result.success
    assert result.status_code == 500
    assert result.error is not None and "500" in result.error


def test_deliver_event_captures_network_error_without_raising() -> None:
    event = _sample_event()

    def unreachable_post(url: str, *, json_body, headers, timeout_seconds) -> int:
        raise urllib.error.URLError("connection refused")

    result = deliver_event(
        event=event,
        api_base_url="http://127.0.0.1:59999",
        http_post_func=unreachable_post,
    )

    assert not result.success
    assert result.status_code is None
    assert result.error is not None


def test_deliver_event_treats_non_2xx_status_as_failure() -> None:
    event = _sample_event()

    result = deliver_event(
        event=event,
        api_base_url="http://127.0.0.1:9000",
        http_post_func=lambda url, **kwargs: 302,
    )

    assert not result.success
    assert result.status_code == 302


def test_deliver_event_rejects_blank_base_url() -> None:
    with pytest.raises(ValueError, match="api_base_url"):
        deliver_event(event=_sample_event(), api_base_url=" ")


# --- Worker ----------------------------------------------------------------


def test_run_outbox_worker_marks_each_event_by_outcome() -> None:
    connection = FakeConnection()
    ok_event = _sample_event()
    bad_event = _sample_event()
    connection.fetchall_result = [_event_row(ok_event), _event_row(bad_event)]

    outcomes = {str(ok_event.event_id): 200, str(bad_event.event_id): 500}

    def mixed_post(url: str, *, json_body, headers, timeout_seconds) -> int:
        if outcomes[json_body["event_id"]] == 500:
            raise urllib.error.HTTPError(url, 500, "boom", None, None)
        return 200

    result = run_outbox_worker(  # type: ignore[arg-type]
        connection,
        api_base_url="http://127.0.0.1:9000",
        max_events=10,
        http_post_func=mixed_post,
    )

    assert result.fetched == 2
    assert result.delivered == 1
    assert result.failed == 1
    update_sql = [sql for sql, _ in connection.executed if "UPDATE drill_lab" in sql]
    assert any("status = 'delivered'" in sql for sql in update_sql)
    assert any("status = 'failed'" in sql for sql in update_sql)
    assert connection.commits == 2  # one commit per mark


def test_run_outbox_worker_with_empty_outbox_is_a_noop() -> None:
    connection = FakeConnection()

    def unexpected_post(url: str, **kwargs: Any) -> int:
        raise AssertionError("no delivery should be attempted")

    result = run_outbox_worker(  # type: ignore[arg-type]
        connection,
        api_base_url="http://127.0.0.1:9000",
        max_events=5,
        http_post_func=unexpected_post,
    )

    assert result == outbox_lab.WorkerResult(fetched=0, delivered=0, failed=0, results=())


def test_run_outbox_worker_rejects_non_positive_max_events() -> None:
    with pytest.raises(ValueError, match="max_events must be > 0"):
        run_outbox_worker(  # type: ignore[arg-type]
            FakeConnection(),
            api_base_url="http://127.0.0.1:9000",
            max_events=0,
        )
