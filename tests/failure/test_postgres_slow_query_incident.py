"""Failure-injection drill: slow query detection and targeted cancellation.

Safety boundary:
- The slow query is a synthetic ``SELECT pg_sleep(...)`` on a dedicated
  connection owned by this drill; it never touches business rows.
- CONTAIN cancels exactly one backend: the PID of the drill's own slow-query
  session. It never cancels or terminates any other session.
- All connections are closed in ``finally`` even when an assertion fails.
"""

import os
import threading
import time

import psycopg2

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.reliability.postgres_diagnostics import load_postgres_diagnostics

LONG_RUNNING_THRESHOLD_SECONDS = 1


def _connect():
    return connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )


def _snapshot(diagnostics_connection):
    return load_postgres_diagnostics(
        diagnostics_connection,
        long_running_threshold_seconds=LONG_RUNNING_THRESHOLD_SECONDS,
        top_query_limit=5,
    )


def _wait_for_slow_query(diagnostics_connection, slow_pid, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = _snapshot(diagnostics_connection)
        if any(
            item.pid == slow_pid and item.state == "active"
            for item in snapshot.long_running_sessions
        ):
            return snapshot
        time.sleep(0.05)
    raise AssertionError(f"slow query pid={slow_pid} was not detected")


def test_slow_query_is_detected_and_cancelled() -> None:
    slow = _connect()
    control = _connect()
    diagnostics = _connect()
    diagnostics.set_session(readonly=True, autocommit=True)

    slow_finished = threading.Event()
    slow_error: list[BaseException] = []

    with slow.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid();")
        slow_pid = int(cursor.fetchone()[0])

    def run_slow_query() -> None:
        try:
            with slow.cursor() as cursor:
                cursor.execute("SELECT pg_sleep(5);")
        except psycopg2.errors.QueryCanceled:
            # Expected: the drill cancels its own query during CONTAIN.
            pass
        except BaseException as exc:  # captured so the main test can assert it
            slow_error.append(exc)
        finally:
            slow_finished.set()

    thread = threading.Thread(target=run_slow_query, daemon=True)
    thread.start()

    try:
        # DETECT: the sleeping query must appear as a long-running active session.
        _wait_for_slow_query(diagnostics, slow_pid)

        # CONTAIN/RECOVER: cancel ONLY the backend PID created by this drill.
        # Per the safety boundary, no other session is ever cancelled.
        with control.cursor() as cursor:
            cursor.execute("SELECT pg_cancel_backend(%s);", (slow_pid,))
            assert cursor.fetchone()[0] is True

        assert slow_finished.wait(timeout=5.0)
        assert not slow_error

        # Cancelling the query leaves the drill's own session in an aborted
        # transaction ("idle in transaction"), which still counts as
        # long-running. Roll back OUR OWN session so it returns to idle
        # before the verification snapshot.
        slow.rollback()

        # VERIFY: a fresh snapshot must no longer list the drill's slow query.
        recovered = _snapshot(diagnostics)
        assert not any(item.pid == slow_pid for item in recovered.long_running_sessions)
    finally:
        # If the drill fails before CONTAIN, cancel our own leftover query so no
        # synthetic state leaks; this still targets only the drill's backend PID.
        try:
            if not slow_finished.is_set():
                with control.cursor() as cursor:
                    cursor.execute("SELECT pg_cancel_backend(%s);", (slow_pid,))
        finally:
            slow.close()
            control.close()
            diagnostics.close()
        thread.join(timeout=5.0)
