import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.reliability.incident_diagnostics import resolve_pipeline_alert


@pytest.fixture
def postgres_connection():
    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )
    connection.autocommit = False
    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def test_incident_resolution_contract_persists_without_internal_commit(
    postgres_connection,
) -> None:
    token = uuid4().hex
    dag_run_id = f"pytest_incident_{token}"
    started_at = datetime(2026, 9, 9, tzinfo=UTC)
    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audit.pipeline_monitoring_runs (
                dag_id, dag_run_id, run_type, started_at, observed_at,
                duration_seconds, status, slow_threshold_seconds
            ) VALUES (%s, %s, 'test', %s, %s, 5, 'failed', 180)
            RETURNING monitoring_run_id;
            """,
            ("ecommerce_ingestion", dag_run_id, started_at, started_at),
        )
        monitoring_run_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO audit.pipeline_alerts (
                monitoring_run_id, dag_id, dag_run_id,
                alert_type, severity, message
            ) VALUES (%s, %s, %s, 'pipeline_failure', 'error', 'synthetic')
            RETURNING pipeline_alert_id;
            """,
            (monitoring_run_id, "ecommerce_ingestion", dag_run_id),
        )
        pipeline_alert_id = cursor.fetchone()[0]

    resolve_pipeline_alert(
        postgres_connection,
        pipeline_alert_id=pipeline_alert_id,
        root_cause_category="configuration",
        root_cause_summary="Synthetic test incident",
        remediation_summary="Corrected synthetic configuration",
        recovery_dag_run_id="pytest_recovery_run",
        verification_summary="Synthetic verification passed",
        resolution_details={"source": "pytest"},
    )
    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT resolved, root_cause_category, recovery_dag_run_id,
                   verification_summary, resolution_details
            FROM audit.pipeline_alerts
            WHERE pipeline_alert_id = %s;
            """,
            (pipeline_alert_id,),
        )
        row = cursor.fetchone()

    assert row[0] is True
    assert row[1] == "configuration"
    assert row[2] == "pytest_recovery_run"
    assert row[3] == "Synthetic verification passed"
    assert row[4]["source"] == "pytest"
