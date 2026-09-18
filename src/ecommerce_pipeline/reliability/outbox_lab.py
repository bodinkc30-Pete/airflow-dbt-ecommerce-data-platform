"""Transactional Outbox / Delivery Guarantee Lab (PART 20.6).

Demonstrates the transactional outbox pattern against a real PostgreSQL
database:

1. A business change (``drill_lab.business_records``) and its outbox event
   (``drill_lab.outbox_events``) are written in ONE database transaction, so
   they commit or roll back together (atomicity — no dual-write gap).
2. A relay worker later fetches pending events with
   ``SELECT ... FOR UPDATE SKIP LOCKED`` and delivers them to an external API
   with an ``Idempotency-Key`` header.
3. Because delivery is at-least-once (network failures, worker restarts, lost
   responses all cause retries), the consumer MUST be idempotent.

Safety boundary: every object created by this lab lives in the ``drill_lab``
schema only. Nothing in the production schemas is touched, and
``drop_lab_schema`` removes all lab objects.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import Json

LAB_SCHEMA = "drill_lab"
BUSINESS_TABLE = f"{LAB_SCHEMA}.business_records"
OUTBOX_TABLE = f"{LAB_SCHEMA}.outbox_events"

STATUS_PENDING = "pending"
STATUS_DELIVERED = "delivered"
STATUS_FAILED = "failed"
VALID_STATUSES = frozenset({STATUS_PENDING, STATUS_DELIVERED, STATUS_FAILED})

DEFAULT_TIMEOUT_SECONDS = 5.0

CREATE_SCHEMA_SQL = f"CREATE SCHEMA IF NOT EXISTS {LAB_SCHEMA};"

CREATE_BUSINESS_TABLE_SQL = f"""
    CREATE TABLE IF NOT EXISTS {BUSINESS_TABLE} (
        business_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        note TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
"""

CREATE_OUTBOX_TABLE_SQL = f"""
    CREATE TABLE IF NOT EXISTS {OUTBOX_TABLE} (
        event_id UUID PRIMARY KEY,
        event_type TEXT NOT NULL,
        payload JSONB NOT NULL DEFAULT '{{}}'::jsonb,
        idempotency_key TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT '{STATUS_PENDING}'
            CHECK (status IN ('{STATUS_PENDING}', '{STATUS_DELIVERED}', '{STATUS_FAILED}')),
        attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        delivered_at TIMESTAMPTZ
    );
"""

DROP_SCHEMA_SQL = f"DROP SCHEMA IF EXISTS {LAB_SCHEMA} CASCADE;"

INSERT_BUSINESS_SQL = f"""
    INSERT INTO {BUSINESS_TABLE} (note)
    VALUES (%s)
    RETURNING business_record_id;
"""

INSERT_OUTBOX_SQL = f"""
    INSERT INTO {OUTBOX_TABLE} (event_id, event_type, payload, idempotency_key)
    VALUES (%s, %s, %s, %s);
"""

FETCH_PENDING_SQL = f"""
    SELECT event_id, event_type, payload, idempotency_key, status, attempts,
           created_at, delivered_at
    FROM {OUTBOX_TABLE}
    WHERE status = '{STATUS_PENDING}'
    ORDER BY created_at, event_id
    FOR UPDATE SKIP LOCKED
    LIMIT %s;
"""

LIST_EVENTS_SQL = f"""
    SELECT event_id, event_type, payload, idempotency_key, status, attempts,
           created_at, delivered_at
    FROM {OUTBOX_TABLE}
    ORDER BY created_at, event_id;
"""

COUNT_BUSINESS_SQL = f"SELECT COUNT(*) FROM {BUSINESS_TABLE};"

MARK_DELIVERED_SQL = f"""
    UPDATE {OUTBOX_TABLE}
    SET status = '{STATUS_DELIVERED}',
        attempts = attempts + 1,
        delivered_at = CURRENT_TIMESTAMP
    WHERE event_id = %s;
"""

MARK_FAILED_SQL = f"""
    UPDATE {OUTBOX_TABLE}
    SET status = '{STATUS_FAILED}',
        attempts = attempts + 1
    WHERE event_id = %s;
"""

REQUEUE_FAILED_SQL = f"""
    UPDATE {OUTBOX_TABLE}
    SET status = '{STATUS_PENDING}'
    WHERE event_id = %s AND status = '{STATUS_FAILED}';
"""


@dataclass(frozen=True)
class OutboxEvent:
    """One row of ``drill_lab.outbox_events``."""

    event_id: UUID
    event_type: str
    payload: dict[str, Any]
    idempotency_key: str
    status: str
    attempts: int
    created_at: datetime
    delivered_at: datetime | None


@dataclass(frozen=True)
class DeliveryResult:
    """Outcome of one HTTP delivery attempt to the external API."""

    event_id: UUID
    success: bool
    status_code: int | None
    error: str | None


@dataclass(frozen=True)
class WorkerResult:
    """Summary of one outbox worker round."""

    fetched: int
    delivered: int
    failed: int
    results: tuple[DeliveryResult, ...]


HttpPostFunc = Callable[..., int]


def _event_from_row(row: tuple[Any, ...]) -> OutboxEvent:
    return OutboxEvent(
        event_id=UUID(str(row[0])),
        event_type=str(row[1]),
        payload=dict(row[2]),
        idempotency_key=str(row[3]),
        status=str(row[4]),
        attempts=int(row[5]),
        created_at=row[6],
        delivered_at=row[7],
    )


def resolve_next_status(*, current_status: str, delivery_succeeded: bool) -> str:
    """Pure state-transition rule for outbox events.

    - ``pending``   -> ``delivered`` on success, ``failed`` on failure.
    - ``failed``    -> ``delivered`` on retry success, stays ``failed`` otherwise.
    - ``delivered`` -> terminal; stays ``delivered`` (re-marking is idempotent).
    """
    if current_status not in VALID_STATUSES:
        raise ValueError(f"Unknown outbox event status: {current_status!r}")
    if current_status == STATUS_DELIVERED:
        return STATUS_DELIVERED
    return STATUS_DELIVERED if delivery_succeeded else STATUS_FAILED


def build_idempotency_key(event_type: str, event_id: UUID) -> str:
    """Derive the unique consumer-facing idempotency key for an event."""
    if not event_type.strip():
        raise ValueError("event_type must be a non-empty string")
    return f"{event_type}:{event_id}"


def create_lab_schema(connection: PgConnection) -> None:
    """Create the ``drill_lab`` schema and both lab tables (idempotent)."""
    with connection.cursor() as cursor:
        cursor.execute(CREATE_SCHEMA_SQL)
        cursor.execute(CREATE_BUSINESS_TABLE_SQL)
        cursor.execute(CREATE_OUTBOX_TABLE_SQL)
    connection.commit()


def drop_lab_schema(connection: PgConnection) -> None:
    """Drop the whole ``drill_lab`` schema (lab cleanup; never touches production)."""
    with connection.cursor() as cursor:
        cursor.execute(DROP_SCHEMA_SQL)
    connection.commit()


def publish_business_event(
    connection: PgConnection,
    *,
    note: str,
    event_type: str,
    payload: dict[str, Any],
) -> UUID:
    """Insert a business record AND its outbox event in ONE transaction.

    Both INSERTs commit together, so it is impossible to persist the business
    change without its event (or vice versa). On any error the whole
    transaction is rolled back and the exception propagates.
    """
    if not note.strip():
        raise ValueError("note must be a non-empty string")
    if not event_type.strip():
        raise ValueError("event_type must be a non-empty string")

    event_id = uuid4()
    idempotency_key = build_idempotency_key(event_type, event_id)
    try:
        with connection.cursor() as cursor:
            cursor.execute(INSERT_BUSINESS_SQL, (note,))
            cursor.execute(
                INSERT_OUTBOX_SQL,
                (str(event_id), event_type, Json(payload), idempotency_key),
            )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return event_id


def fetch_pending_events(connection: PgConnection, *, limit: int = 100) -> list[OutboxEvent]:
    """Fetch pending events, locking rows with FOR UPDATE SKIP LOCKED.

    SKIP LOCKED lets multiple worker processes poll the same outbox table
    without blocking each other or double-processing the same row.
    """
    if limit <= 0:
        raise ValueError("limit must be > 0")
    with connection.cursor() as cursor:
        cursor.execute(FETCH_PENDING_SQL, (limit,))
        rows = cursor.fetchall()
    return [_event_from_row(row) for row in rows]


def list_outbox_events(connection: PgConnection) -> list[OutboxEvent]:
    """Return every outbox event (drill verification helper)."""
    with connection.cursor() as cursor:
        cursor.execute(LIST_EVENTS_SQL)
        rows = cursor.fetchall()
    return [_event_from_row(row) for row in rows]


def count_business_records(connection: PgConnection) -> int:
    """Return the number of business records (drill verification helper)."""
    with connection.cursor() as cursor:
        cursor.execute(COUNT_BUSINESS_SQL)
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError("business record count query returned no row")
    return int(row[0])


def mark_delivered(connection: PgConnection, event_id: UUID) -> None:
    """Mark an event delivered; increments ``attempts`` and sets ``delivered_at``."""
    with connection.cursor() as cursor:
        cursor.execute(MARK_DELIVERED_SQL, (str(event_id),))
    connection.commit()


def mark_failed(connection: PgConnection, event_id: UUID, error: str) -> None:
    """Mark an event failed; increments ``attempts`` and keeps it retryable."""
    with connection.cursor() as cursor:
        cursor.execute(MARK_FAILED_SQL, (str(event_id),))
    connection.commit()


def requeue_failed_event(connection: PgConnection, event_id: UUID) -> None:
    """Move a ``failed`` event back to ``pending`` so a worker retries it."""
    with connection.cursor() as cursor:
        cursor.execute(REQUEUE_FAILED_SQL, (str(event_id),))
    connection.commit()


def default_http_post(
    url: str,
    *,
    json_body: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: float,
) -> int:
    """POST ``json_body`` as JSON and return the HTTP status code (>=400 raises)."""
    request = urllib.request.Request(
        url,
        data=json.dumps(json_body).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return int(response.status)


def deliver_event(
    *,
    event: OutboxEvent,
    api_base_url: str,
    http_post_func: HttpPostFunc = default_http_post,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> DeliveryResult:
    """Deliver one event to the external API with an Idempotency-Key header.

    Never raises for delivery problems: network errors, timeouts and non-2xx
    responses are captured in the returned ``DeliveryResult`` so the caller can
    mark the event failed and retry later.
    """
    if not api_base_url.strip():
        raise ValueError("api_base_url must be a non-empty string")
    url = f"{api_base_url.rstrip('/')}/invoice"
    headers = {"Idempotency-Key": event.idempotency_key}
    body = {
        "event_id": str(event.event_id),
        "event_type": event.event_type,
        "payload": event.payload,
    }
    try:
        status_code = http_post_func(
            url,
            json_body=body,
            headers=headers,
            timeout_seconds=timeout_seconds,
        )
    except urllib.error.HTTPError as exc:
        return DeliveryResult(
            event_id=event.event_id,
            success=False,
            status_code=int(exc.code),
            error=f"HTTP {exc.code}: {exc.reason}",
        )
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return DeliveryResult(
            event_id=event.event_id,
            success=False,
            status_code=None,
            error=str(exc),
        )
    success = 200 <= status_code < 300
    return DeliveryResult(
        event_id=event.event_id,
        success=success,
        status_code=status_code,
        error=None if success else f"unexpected HTTP status {status_code}",
    )


def run_outbox_worker(
    connection: PgConnection,
    *,
    api_base_url: str,
    max_events: int = 100,
    http_post_func: HttpPostFunc = default_http_post,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> WorkerResult:
    """Run ONE worker round: fetch pending events, deliver each, mark the result.

    - Successful deliveries are marked ``delivered``.
    - Failed deliveries are marked ``failed`` (retryable via
      ``requeue_failed_event``); nothing is ever deleted or lost.
    """
    if max_events <= 0:
        raise ValueError("max_events must be > 0")

    events = fetch_pending_events(connection, limit=max_events)
    results: list[DeliveryResult] = []
    for event in events:
        result = deliver_event(
            event=event,
            api_base_url=api_base_url,
            http_post_func=http_post_func,
            timeout_seconds=timeout_seconds,
        )
        results.append(result)
        if result.success:
            mark_delivered(connection, event.event_id)
        else:
            mark_failed(connection, event.event_id, result.error or "unknown delivery error")

    delivered = sum(1 for item in results if item.success)
    return WorkerResult(
        fetched=len(events),
        delivered=delivered,
        failed=len(results) - delivered,
        results=tuple(results),
    )
