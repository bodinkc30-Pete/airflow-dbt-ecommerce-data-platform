"""Failure-injection drill: connection failure and recovery.

Safety boundary:
- The injected failure targets a closed port on localhost only; nothing is
  terminated or modified on the real PostgreSQL instance.
- Recovery connects through the standard ``connect_postgres`` helper using the
  same environment variables as the pipeline.
"""

import os

import psycopg2
import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.reliability.postgres_diagnostics import load_postgres_diagnostics

CLOSED_PORT = 59999


def _connect():
    return connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )


def test_connection_failure_is_detected_and_recovers() -> None:
    connection = None
    try:
        # INJECT: connect to a port where nothing listens. This must fail.
        with pytest.raises(psycopg2.OperationalError):
            connect_postgres(
                host="localhost",
                port=CLOSED_PORT,
                database=os.getenv("POSTGRES_DB", "ecommerce"),
                user=os.getenv("POSTGRES_USER", "airflow"),
                password=os.getenv("POSTGRES_PASSWORD", "change_me"),
            )

        # RECOVER: connect to the real PostgreSQL and run a trivial query.
        connection = _connect()
        connection.set_session(readonly=True, autocommit=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            assert cursor.fetchone()[0] == 1

        # VERIFY: the diagnostics layer works end to end, proving the pipeline
        # is fully usable again after the injected connection failure.
        snapshot = load_postgres_diagnostics(
            connection,
            long_running_threshold_seconds=60,
            top_query_limit=5,
        )
        assert snapshot.database == os.getenv("POSTGRES_DB", "ecommerce")
        assert snapshot.connections.total >= 1
    finally:
        if connection is not None:
            connection.close()
