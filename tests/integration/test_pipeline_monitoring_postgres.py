import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.monitoring.pipeline_monitoring import (
    build_pipeline_alerts,
    build_pipeline_snapshot,
    load_ingestion_telemetry,
    record_pipeline_alerts,
    record_pipeline_monitoring_run,
    update_alert_delivery,
)


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


def test_monitoring_snapshot_and_alerts_persist_transaction_neutral(
    postgres_connection,
) -> None:
    token = uuid4().hex
    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audit.ingestion_runs (
                pipeline_name, run_type, status,
                files_discovered, files_processed, files_failed,
                rows_discovered, rows_loaded, rows_rejected
            ) VALUES (%s, 'test', 'success', 2, 1, 1, 10, 8, 2)
            RETURNING ingestion_run_id;
            """,
            (f"pytest_monitoring_{token}",),
        )
        ingestion_run_id = cursor.fetchone()[0]
        cursor.execute(
            """
            INSERT INTO audit.schema_events (
                ingestion_run_id, source_name, event_type, severity
            ) VALUES (%s, 'orders', 'missing_column', 'error');
            """,
            (ingestion_run_id,),
        )
        cursor.execute(
            """
            INSERT INTO audit.data_quality_results (
                ingestion_run_id, source_name, check_name,
                check_category, status, rows_checked, rows_failed
            ) VALUES
                (%s, 'orders', 'blocking_check', 'record', 'fail', 10, 1),
                (%s, 'orders', 'warning_check', 'record', 'warning', 10, 2);
            """,
            (ingestion_run_id, ingestion_run_id),
        )

    telemetry = load_ingestion_telemetry(postgres_connection, ingestion_run_id)
    assert telemetry.files_discovered == 2
    assert telemetry.rows_loaded == 8
    assert telemetry.schema_error_count == 1
    assert telemetry.dq_fail_count == 1
    assert telemetry.dq_warning_count == 1

    started_at = datetime(2026, 9, 9, tzinfo=UTC)
    snapshot = build_pipeline_snapshot(
        dag_id="ecommerce_ingestion",
        dag_run_id=f"pytest_monitoring_{token}",
        run_type="test",
        ingestion_run_id=ingestion_run_id,
        started_at=started_at,
        observed_at=started_at + timedelta(seconds=240),
        slow_threshold_seconds=180,
        task_states={"dbt_test_blocking": "failed", "dbt_test_warning": "upstream_failed"},
        ingestion=telemetry,
        dbt_freshness_summary={"pass": 7, "warn": 1, "error": 0},
        dbt_blocking_summary={"pass": 205, "warn": 0, "error": 2},
        dbt_warning_summary={"pass": 10, "warn": 7, "error": 0},
    )
    alerts = build_pipeline_alerts(snapshot)

    monitoring_run_id = record_pipeline_monitoring_run(
        postgres_connection,
        snapshot,
    )
    alert_ids = record_pipeline_alerts(
        postgres_connection,
        monitoring_run_id=monitoring_run_id,
        snapshot=snapshot,
        alerts=alerts,
    )

    update_alert_delivery(
        postgres_connection,
        pipeline_alert_id=alert_ids[0],
        status="not_configured",
    )

    assert len(alert_ids) == 7
    assert record_pipeline_monitoring_run(postgres_connection, snapshot) == monitoring_run_id

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT status, is_slow, rows_loaded, schema_error_count,
                   ingestion_dq_fail_count, dbt_warning_count,
                   failed_task_count, blocked_task_count
            FROM audit.pipeline_monitoring_runs
            WHERE monitoring_run_id = %s;
            """,
            (monitoring_run_id,),
        )
        row = cursor.fetchone()
        cursor.execute(
            """
            SELECT COUNT(*), COUNT(*) FILTER (
                WHERE delivery_status = 'not_configured'
            )
            FROM audit.pipeline_alerts
            WHERE monitoring_run_id = %s;
            """,
            (monitoring_run_id,),
        )
        alert_counts = cursor.fetchone()

    assert row == ("failed", True, 8, 1, 1, 7, 1, 1)
    assert alert_counts == (7, 1)
