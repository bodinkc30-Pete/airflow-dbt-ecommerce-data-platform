from datetime import UTC, datetime

import pytest

from ecommerce_pipeline.reliability.incident_diagnostics import (
    load_pipeline_run_diagnostics,
    resolve_pipeline_alert,
)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params):
        self.connection.queries.append((query, params))
        if "FROM dag_run" in query:
            self.rows = [(
                "success", "manual",
                datetime(2026, 9, 9, tzinfo=UTC),
                datetime(2026, 9, 9, 0, 4, tzinfo=UTC),
                240.0,
            )]
        elif "FROM task_instance" in query:
            self.rows = [("dbt_run_transformations", "success", 2, 2, 11.0)]
        elif "FROM audit.pipeline_monitoring_runs" in query:
            self.rows = [(1400, "success", True, 0, 0, "success")]
        elif "FROM audit.pipeline_alerts" in query:
            self.rows = [(12, "slow_pipeline", "warning", "not_configured", False, None)]
        elif "UPDATE audit.pipeline_alerts" in query:
            self.rows = [(params[-1],)]
        else:
            raise AssertionError(query)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class FakeConnection:
    def __init__(self):
        self.queries = []

    def cursor(self):
        return FakeCursor(self)


def test_load_pipeline_run_diagnostics_combines_control_planes() -> None:
    app = FakeConnection()
    airflow = FakeConnection()
    result = load_pipeline_run_diagnostics(
        application_connection=app,
        airflow_connection=airflow,
        dag_id="ecommerce_ingestion",
        dag_run_id="retry_run",
    )
    assert result.run_state == "success"
    assert result.run_type == "manual"
    assert result.duration_seconds == 240.0
    assert result.ingestion_run_id == 1400
    assert result.ingestion_status == "success"
    assert result.monitoring_status == "success"
    assert result.monitoring_is_slow is True
    assert result.tasks[0].task_id == "dbt_run_transformations"
    assert result.tasks[0].try_number == 2
    assert result.alerts[0].alert_type == "slow_pipeline"


def test_resolve_pipeline_alert_validates_required_text() -> None:
    connection = FakeConnection()
    with pytest.raises(ValueError, match="root_cause_summary"):
        resolve_pipeline_alert(
            connection,
            pipeline_alert_id=1,
            root_cause_category="transient_dependency",
            root_cause_summary=" ",
            remediation_summary="Retry succeeded",
            recovery_dag_run_id="retry_run",
            verification_summary="Pipeline success",
        )


def test_resolve_pipeline_alert_updates_without_committing() -> None:
    connection = FakeConnection()
    resolve_pipeline_alert(
        connection,
        pipeline_alert_id=12,
        root_cause_category="transient_dependency",
        root_cause_summary="Synthetic first-attempt dbt failure",
        remediation_summary="Airflow retried the idempotent dbt run",
        recovery_dag_run_id="retry_run",
        verification_summary="DagRun and downstream DQ succeeded",
        resolution_details={"try_number": 2},
    )
    assert any("UPDATE audit.pipeline_alerts" in query for query, _ in connection.queries)
    assert not hasattr(connection, "commit")
