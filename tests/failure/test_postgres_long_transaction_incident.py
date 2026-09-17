"""Failure-injection drill: long-running transaction detection and recovery.

Safety boundary:
- The transaction only performs a SELECT on a catalog function; it never
  modifies business rows.
- Recovery is a plain ROLLBACK of the drill's own transaction.
- All connections are closed in ``finally`` even when an assertion fails.
"""

import os
import time

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


def test_long_running_transaction_is_detected_and_recovers() -> None:
    transaction = _connect()
    diagnostics = _connect()
    diagnostics.set_session(readonly=True, autocommit=True)

    try:
        # INJECT: open a transaction and hold it past the diagnostics threshold.
        with transaction.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid();")
            transaction_pid = int(cursor.fetchone()[0])
            # psycopg2 opens an implicit transaction here (autocommit is off);
            # the SELECT touches no business rows and the transaction is held
            # open past the diagnostics threshold.
            cursor.execute("SELECT 1;")

        # Let the transaction age beyond the long-running threshold.
        time.sleep(LONG_RUNNING_THRESHOLD_SECONDS + 0.2)

        # DETECT: the aged transaction must appear in the diagnostics snapshot.
        detected = _snapshot(diagnostics)
        assert any(
            item.pid == transaction_pid and item.state == "idle in transaction"
            for item in detected.long_running_sessions
        ), f"transaction pid={transaction_pid} not detected: {detected.long_running_sessions}"
        assert detected.connections.idle_in_transaction >= 1

        # RECOVER: roll back only the drill's own transaction.
        transaction.rollback()

        # VERIFY: a fresh snapshot must no longer list the drill's transaction.
        recovered = _snapshot(diagnostics)
        assert not any(
            item.pid == transaction_pid for item in recovered.long_running_sessions
        )
    finally:
        # ROLLBACK is idempotent for a closed transaction; guarantee no state leaks.
        try:
            transaction.rollback()
        finally:
            transaction.close()
            diagnostics.close()
