from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import Json

RootCauseCategory = Literal[
    "transient_dependency",
    "database",
    "data_quality",
    "schema",
    "transformation",
    "orchestration",
    "timeout",
    "resource",
    "configuration",
    "unknown",
]

_ALLOWED_ROOT_CAUSE_CATEGORIES = {
    "transient_dependency",
    "database",
    "data_quality",
    "schema",
    "transformation",
    "orchestration",
    "timeout",
    "resource",
    "configuration",
    "unknown",
}


@dataclass(frozen=True)
class TaskDiagnostic:
    task_id: str
    state: str
    try_number: int
    max_tries: int
    duration_seconds: float | None


@dataclass(frozen=True)
class AlertDiagnostic:
    pipeline_alert_id: int
    alert_type: str
    severity: str
    delivery_status: str
    resolved: bool
    root_cause_category: str | None


@dataclass(frozen=True)
class PipelineRunDiagnostics:
    dag_id: str
    dag_run_id: str
    run_state: str
    run_type: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: float | None
    ingestion_run_id: int | None
    ingestion_status: str | None
    monitoring_status: str | None
    monitoring_is_slow: bool | None
    failed_task_count: int
    blocked_task_count: int
    tasks: tuple[TaskDiagnostic, ...]
    alerts: tuple[AlertDiagnostic, ...]


def _load_airflow_run(
    connection: PgConnection,
    *,
    dag_id: str,
    dag_run_id: str,
) -> tuple[str, str, datetime | None, datetime | None, float | None]:
    query = """
        SELECT state, run_type, start_date, end_date,
               CASE
                   WHEN start_date IS NOT NULL
                    AND end_date IS NOT NULL
                    AND end_date >= start_date
                   THEN EXTRACT(EPOCH FROM (end_date - start_date))::double precision
                   ELSE NULL
               END
        FROM dag_run
        WHERE dag_id = %s AND run_id = %s;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (dag_id, dag_run_id))
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"DagRun not found: dag_id={dag_id!r}, run_id={dag_run_id!r}")
    return str(row[0]), str(row[1]), row[2], row[3], row[4]


def _load_task_diagnostics(
    connection: PgConnection,
    *,
    dag_id: str,
    dag_run_id: str,
) -> tuple[TaskDiagnostic, ...]:
    query = """
        SELECT task_id, COALESCE(state, 'none'), try_number, max_tries,
               CASE WHEN duration >= 0 THEN duration ELSE NULL END
        FROM task_instance
        WHERE dag_id = %s AND run_id = %s
        ORDER BY task_id;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (dag_id, dag_run_id))
        rows = cursor.fetchall()
    return tuple(
        TaskDiagnostic(
            task_id=str(row[0]),
            state=str(row[1]),
            try_number=int(row[2]),
            max_tries=int(row[3]),
            duration_seconds=float(row[4]) if row[4] is not None else None,
        )
        for row in rows
    )


def _load_application_observability(
    connection: PgConnection,
    *,
    dag_id: str,
    dag_run_id: str,
) -> tuple[int | None, str | None, bool | None, int, int, str | None]:
    query = """
        SELECT m.ingestion_run_id, m.status, m.is_slow,
               m.failed_task_count, m.blocked_task_count, r.status
        FROM audit.pipeline_monitoring_runs m
        LEFT JOIN audit.ingestion_runs r
          ON r.ingestion_run_id = m.ingestion_run_id
        WHERE m.dag_id = %s AND m.dag_run_id = %s;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (dag_id, dag_run_id))
        row = cursor.fetchone()
    if row is None:
        return None, None, None, 0, 0, None
    return (
        int(row[0]) if row[0] is not None else None,
        str(row[1]),
        bool(row[2]),
        int(row[3]),
        int(row[4]),
        str(row[5]) if row[5] is not None else None,
    )


def _load_alerts(
    connection: PgConnection,
    *,
    dag_id: str,
    dag_run_id: str,
) -> tuple[AlertDiagnostic, ...]:
    query = """
        SELECT pipeline_alert_id, alert_type, severity, delivery_status,
               resolved, root_cause_category
        FROM audit.pipeline_alerts
        WHERE dag_id = %s AND dag_run_id = %s
        ORDER BY pipeline_alert_id;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (dag_id, dag_run_id))
        rows = cursor.fetchall()
    return tuple(
        AlertDiagnostic(
            pipeline_alert_id=int(row[0]),
            alert_type=str(row[1]),
            severity=str(row[2]),
            delivery_status=str(row[3]),
            resolved=bool(row[4]),
            root_cause_category=str(row[5]) if row[5] is not None else None,
        )
        for row in rows
    )


def load_pipeline_run_diagnostics(
    *,
    application_connection: PgConnection,
    airflow_connection: PgConnection,
    dag_id: str,
    dag_run_id: str,
) -> PipelineRunDiagnostics:
    run_state, run_type, started_at, ended_at, duration_seconds = _load_airflow_run(
        airflow_connection,
        dag_id=dag_id,
        dag_run_id=dag_run_id,
    )
    tasks = _load_task_diagnostics(
        airflow_connection,
        dag_id=dag_id,
        dag_run_id=dag_run_id,
    )
    (
        ingestion_run_id,
        monitoring_status,
        monitoring_is_slow,
        failed_task_count,
        blocked_task_count,
        ingestion_status,
    ) = _load_application_observability(
        application_connection,
        dag_id=dag_id,
        dag_run_id=dag_run_id,
    )
    alerts = _load_alerts(
        application_connection,
        dag_id=dag_id,
        dag_run_id=dag_run_id,
    )
    return PipelineRunDiagnostics(
        dag_id=dag_id,
        dag_run_id=dag_run_id,
        run_state=run_state,
        run_type=run_type,
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        ingestion_run_id=ingestion_run_id,
        ingestion_status=ingestion_status,
        monitoring_status=monitoring_status,
        monitoring_is_slow=monitoring_is_slow,
        failed_task_count=failed_task_count,
        blocked_task_count=blocked_task_count,
        tasks=tasks,
        alerts=alerts,
    )


def _required_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def resolve_pipeline_alert(
    connection: PgConnection,
    *,
    pipeline_alert_id: int,
    root_cause_category: RootCauseCategory,
    root_cause_summary: str,
    remediation_summary: str,
    recovery_dag_run_id: str,
    verification_summary: str,
    resolution_details: Mapping[str, Any] | None = None,
) -> None:
    if root_cause_category not in _ALLOWED_ROOT_CAUSE_CATEGORIES:
        raise ValueError(f"Unsupported root_cause_category: {root_cause_category}")
    root_cause_summary = _required_text(
        root_cause_summary, field_name="root_cause_summary"
    )
    remediation_summary = _required_text(
        remediation_summary, field_name="remediation_summary"
    )
    recovery_dag_run_id = _required_text(
        recovery_dag_run_id, field_name="recovery_dag_run_id"
    )
    verification_summary = _required_text(
        verification_summary, field_name="verification_summary"
    )
    query = """
        UPDATE audit.pipeline_alerts
        SET resolved = TRUE,
            resolved_at = CURRENT_TIMESTAMP,
            root_cause_category = %s,
            root_cause_summary = %s,
            remediation_summary = %s,
            recovery_dag_run_id = %s,
            verification_summary = %s,
            resolution_details = %s
        WHERE pipeline_alert_id = %s
          AND resolved = FALSE
        RETURNING pipeline_alert_id;
    """
    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                root_cause_category,
                root_cause_summary,
                remediation_summary,
                recovery_dag_run_id,
                verification_summary,
                Json(dict(resolution_details or {})),
                pipeline_alert_id,
            ),
        )
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError(
            "Alert not found or already resolved: "
            f"pipeline_alert_id={pipeline_alert_id}"
        )


def diagnostics_to_dict(diagnostics: PipelineRunDiagnostics) -> dict[str, Any]:
    def iso(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    return {
        "dag_id": diagnostics.dag_id,
        "dag_run_id": diagnostics.dag_run_id,
        "run_state": diagnostics.run_state,
        "run_type": diagnostics.run_type,
        "started_at": iso(diagnostics.started_at),
        "ended_at": iso(diagnostics.ended_at),
        "duration_seconds": diagnostics.duration_seconds,
        "ingestion_run_id": diagnostics.ingestion_run_id,
        "ingestion_status": diagnostics.ingestion_status,
        "monitoring_status": diagnostics.monitoring_status,
        "monitoring_is_slow": diagnostics.monitoring_is_slow,
        "failed_task_count": diagnostics.failed_task_count,
        "blocked_task_count": diagnostics.blocked_task_count,
        "tasks": [
            {
                "task_id": task.task_id,
                "state": task.state,
                "try_number": task.try_number,
                "max_tries": task.max_tries,
                "duration_seconds": task.duration_seconds,
            }
            for task in diagnostics.tasks
        ],
        "alerts": [
            {
                "pipeline_alert_id": alert.pipeline_alert_id,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "delivery_status": alert.delivery_status,
                "resolved": alert.resolved,
                "root_cause_category": alert.root_cause_category,
            }
            for alert in diagnostics.alerts
        ],
    }
