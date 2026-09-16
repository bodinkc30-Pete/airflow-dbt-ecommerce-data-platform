import os

import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.reliability.postgres_diagnostics import load_postgres_diagnostics


@pytest.fixture
def postgres_connection():
    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )
    connection.set_session(readonly=True, autocommit=True)
    try:
        yield connection
    finally:
        connection.close()


def test_postgres_diagnostics_reads_live_operational_state(postgres_connection) -> None:
    snapshot = load_postgres_diagnostics(
        postgres_connection,
        long_running_threshold_seconds=60,
        top_query_limit=5,
    )

    assert snapshot.database == os.getenv("POSTGRES_DB", "ecommerce")
    assert snapshot.server_version
    assert snapshot.connections.total >= 1
    assert snapshot.connections.max_connections > 0
    assert 0 <= snapshot.connections.usage_percent <= 100
    assert all(item.blocked_seconds >= 0 for item in snapshot.blocking_sessions)
    assert all(item.duration_seconds >= 0 for item in snapshot.long_running_sessions)
    assert len(snapshot.top_queries) <= 5
    assert all(item.calls >= 0 for item in snapshot.top_queries)
