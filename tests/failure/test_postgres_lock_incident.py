import os
import threading
import time

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.reliability.postgres_diagnostics import load_postgres_diagnostics


def _connect():
    return connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )


def _wait_for_blocker(diagnostics_connection, blocker_pid, waiter_pid, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = load_postgres_diagnostics(
            diagnostics_connection,
            long_running_threshold_seconds=1,
            top_query_limit=5,
        )
        if any(
            item.blocked_pid == waiter_pid and item.blocker_pid == blocker_pid
            for item in snapshot.blocking_sessions
        ):
            return snapshot
        time.sleep(0.05)
    raise AssertionError("PostgreSQL blocking relationship was not detected")


def test_advisory_lock_incident_is_detected_and_recovers() -> None:
    lock_key = 62020001
    blocker = _connect()
    waiter = _connect()
    diagnostics = _connect()
    diagnostics.set_session(readonly=True, autocommit=True)

    waiter_finished = threading.Event()
    waiter_error: list[BaseException] = []

    with blocker.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid();")
        blocker_pid = int(cursor.fetchone()[0])
        cursor.execute("SELECT pg_advisory_lock(%s);", (lock_key,))

    with waiter.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid();")
        waiter_pid = int(cursor.fetchone()[0])

    def wait_on_lock() -> None:
        try:
            with waiter.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s);", (lock_key,))
                cursor.execute("SELECT pg_advisory_unlock(%s);", (lock_key,))
        except BaseException as exc:  # captured so the main test can assert it
            waiter_error.append(exc)
        finally:
            waiter_finished.set()

    thread = threading.Thread(target=wait_on_lock, daemon=True)
    thread.start()

    try:
        snapshot = _wait_for_blocker(
            diagnostics,
            blocker_pid=blocker_pid,
            waiter_pid=waiter_pid,
        )
        assert snapshot.connections.waiting >= 1

        time.sleep(1.1)
        aged_snapshot = load_postgres_diagnostics(
            diagnostics,
            long_running_threshold_seconds=1,
            top_query_limit=5,
        )
        assert any(
            item.pid == waiter_pid and item.wait_event_type == "Lock"
            for item in aged_snapshot.long_running_sessions
        )

        with blocker.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s);", (lock_key,))

        assert waiter_finished.wait(timeout=5.0)
        assert not waiter_error

        recovered = load_postgres_diagnostics(
            diagnostics,
            long_running_threshold_seconds=1,
            top_query_limit=5,
        )
        assert not any(
            item.blocked_pid == waiter_pid
            for item in recovered.blocking_sessions
        )
    finally:
        try:
            with blocker.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock_all();")
        finally:
            blocker.close()
            waiter.close()
            diagnostics.close()
