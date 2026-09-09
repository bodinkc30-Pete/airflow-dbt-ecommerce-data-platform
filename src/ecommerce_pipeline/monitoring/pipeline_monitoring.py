import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import Json

PipelineStatus = Literal["success", "failed"]
AlertSeverity = Literal["warning", "error", "critical"]
DeliveryStatus = Literal["recorded", "not_configured", "sent", "failed"]


@dataclass(frozen=True)
class IngestionTelemetry:
    files_discovered: int = 0
    files_processed: int = 0
    files_failed: int = 0
    rows_discovered: int = 0
    rows_loaded: int = 0
    rows_rejected: int = 0
    schema_error_count: int = 0
    schema_warning_count: int = 0
    dq_fail_count: int = 0
    dq_warning_count: int = 0


@dataclass(frozen=True)
class PipelineMonitoringSnapshot:
    dag_id: str
    dag_run_id: str
    run_type: str
    ingestion_run_id: int | None
    started_at: datetime
    observed_at: datetime
    duration_seconds: float
    status: PipelineStatus
    is_slow: bool
    slow_threshold_seconds: int
    ingestion: IngestionTelemetry
    dbt_freshness_warning_count: int
    dbt_blocking_error_count: int
    dbt_warning_count: int
    failed_task_count: int
    blocked_task_count: int
    task_states: Mapping[str, str]
    dbt_summary: Mapping[str, Any] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineAlert:
    alert_type: str
    severity: AlertSeverity
    message: str
    external_notification_requested: bool
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WebhookDeliveryResult:
    status: DeliveryStatus
    error: str | None = None


def classify_pipeline_status(task_states: Mapping[str, str]) -> PipelineStatus:
    if not task_states:
        return "failed"
    return "success" if all(state == "success" for state in task_states.values()) else "failed"


def _summary_count(summary: Mapping[str, Any] | None, key: str) -> int:
    if not summary:
        return 0
    value = summary.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Invalid dbt summary count for {key}: {value!r}")
    return value


def load_ingestion_telemetry(
    connection: PgConnection,
    ingestion_run_id: int | None,
) -> IngestionTelemetry:
    if ingestion_run_id is None:
        return IngestionTelemetry()

    query = """
        SELECT
            r.files_discovered,
            r.files_processed,
            r.files_failed,
            r.rows_discovered,
            r.rows_loaded,
            r.rows_rejected,
            (
                SELECT COUNT(*)
                FROM audit.schema_events s
                WHERE s.ingestion_run_id = r.ingestion_run_id
                  AND s.severity IN ('error', 'critical')
            ),
            (
                SELECT COUNT(*)
                FROM audit.schema_events s
                WHERE s.ingestion_run_id = r.ingestion_run_id
                  AND s.severity = 'warning'
            ),
            (
                SELECT COUNT(*)
                FROM audit.data_quality_results d
                WHERE d.ingestion_run_id = r.ingestion_run_id
                  AND d.status = 'fail'
            ),
            (
                SELECT COUNT(*)
                FROM audit.data_quality_results d
                WHERE d.ingestion_run_id = r.ingestion_run_id
                  AND d.status = 'warning'
            )
        FROM audit.ingestion_runs r
        WHERE r.ingestion_run_id = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (ingestion_run_id,))
        row = cursor.fetchone()

    if row is None:
        raise RuntimeError(
            "Ingestion run not found for monitoring: "
            f"ingestion_run_id={ingestion_run_id}"
        )

    return IngestionTelemetry(
        files_discovered=int(row[0]),
        files_processed=int(row[1]),
        files_failed=int(row[2]),
        rows_discovered=int(row[3]),
        rows_loaded=int(row[4]),
        rows_rejected=int(row[5]),
        schema_error_count=int(row[6]),
        schema_warning_count=int(row[7]),
        dq_fail_count=int(row[8]),
        dq_warning_count=int(row[9]),
    )


def build_pipeline_snapshot(
    *,
    dag_id: str,
    dag_run_id: str,
    run_type: str,
    ingestion_run_id: int | None,
    started_at: datetime,
    observed_at: datetime,
    slow_threshold_seconds: int,
    task_states: Mapping[str, str],
    ingestion: IngestionTelemetry,
    dbt_freshness_summary: Mapping[str, Any] | None = None,
    dbt_blocking_summary: Mapping[str, Any] | None = None,
    dbt_warning_summary: Mapping[str, Any] | None = None,
) -> PipelineMonitoringSnapshot:
    if slow_threshold_seconds <= 0:
        raise ValueError("slow_threshold_seconds must be > 0")

    duration_seconds = max(
        0.0,
        (observed_at - started_at).total_seconds(),
    )
    status = classify_pipeline_status(task_states)
    failed_task_count = sum(state == "failed" for state in task_states.values())
    blocked_task_count = sum(
        state == "upstream_failed" for state in task_states.values()
    )

    dbt_summary = {
        "freshness": dict(dbt_freshness_summary or {}),
        "blocking": dict(dbt_blocking_summary or {}),
        "warning": dict(dbt_warning_summary or {}),
    }

    return PipelineMonitoringSnapshot(
        dag_id=dag_id,
        dag_run_id=dag_run_id,
        run_type=run_type,
        ingestion_run_id=ingestion_run_id,
        started_at=started_at,
        observed_at=observed_at,
        duration_seconds=duration_seconds,
        status=status,
        is_slow=duration_seconds > slow_threshold_seconds,
        slow_threshold_seconds=slow_threshold_seconds,
        ingestion=ingestion,
        dbt_freshness_warning_count=_summary_count(
            dbt_freshness_summary, "warn"
        ),
        dbt_blocking_error_count=_summary_count(
            dbt_blocking_summary, "error"
        ),
        dbt_warning_count=_summary_count(dbt_warning_summary, "warn"),
        failed_task_count=failed_task_count,
        blocked_task_count=blocked_task_count,
        task_states=dict(task_states),
        dbt_summary=dbt_summary,
    )


def build_pipeline_alerts(
    snapshot: PipelineMonitoringSnapshot,
    *,
    notify_warnings: bool = False,
) -> tuple[PipelineAlert, ...]:
    alerts: list[PipelineAlert] = []

    if snapshot.status == "failed":
        alerts.append(
            PipelineAlert(
                alert_type="pipeline_failure",
                severity="error",
                message=(
                    f"Pipeline {snapshot.dag_id} failed for "
                    f"DagRun {snapshot.dag_run_id}"
                ),
                external_notification_requested=True,
                details={
                    "failed_task_count": snapshot.failed_task_count,
                    "blocked_task_count": snapshot.blocked_task_count,
                },
            )
        )

    if snapshot.is_slow:
        alerts.append(
            PipelineAlert(
                alert_type="slow_pipeline",
                severity="warning",
                message=(
                    f"Pipeline {snapshot.dag_id} exceeded slow threshold: "
                    f"{snapshot.duration_seconds:.1f}s > "
                    f"{snapshot.slow_threshold_seconds}s"
                ),
                external_notification_requested=True,
                details={
                    "duration_seconds": snapshot.duration_seconds,
                    "slow_threshold_seconds": snapshot.slow_threshold_seconds,
                },
            )
        )

    if snapshot.ingestion.schema_error_count > 0:
        alerts.append(
            PipelineAlert(
                alert_type="schema_drift",
                severity="error",
                message=(
                    "Schema drift errors detected: "
                    f"{snapshot.ingestion.schema_error_count}"
                ),
                external_notification_requested=True,
                details={"count": snapshot.ingestion.schema_error_count},
            )
        )

    if snapshot.ingestion.dq_fail_count > 0:
        alerts.append(
            PipelineAlert(
                alert_type="data_quality_failure",
                severity="error",
                message=(
                    "Blocking ingestion data-quality failures detected: "
                    f"{snapshot.ingestion.dq_fail_count}"
                ),
                external_notification_requested=True,
                details={"count": snapshot.ingestion.dq_fail_count},
            )
        )

    if snapshot.ingestion.dq_warning_count > 0:
        alerts.append(
            PipelineAlert(
                alert_type="data_quality_warning",
                severity="warning",
                message=(
                    "Ingestion data-quality warnings detected: "
                    f"{snapshot.ingestion.dq_warning_count}"
                ),
                external_notification_requested=notify_warnings,
                details={"count": snapshot.ingestion.dq_warning_count},
            )
        )

    if snapshot.dbt_freshness_warning_count > 0:
        alerts.append(
            PipelineAlert(
                alert_type="dbt_freshness_warning",
                severity="warning",
                message=(
                    "dbt source freshness warnings detected: "
                    f"{snapshot.dbt_freshness_warning_count}"
                ),
                external_notification_requested=notify_warnings,
                details={"count": snapshot.dbt_freshness_warning_count},
            )
        )

    if snapshot.dbt_warning_count > 0:
        alerts.append(
            PipelineAlert(
                alert_type="dbt_warning",
                severity="warning",
                message=(
                    "dbt warning-tier quality checks detected: "
                    f"{snapshot.dbt_warning_count}"
                ),
                external_notification_requested=notify_warnings,
                details={"count": snapshot.dbt_warning_count},
            )
        )

    return tuple(alerts)


def record_pipeline_monitoring_run(
    connection: PgConnection,
    snapshot: PipelineMonitoringSnapshot,
) -> int:
    query = """
        INSERT INTO audit.pipeline_monitoring_runs (
            dag_id, dag_run_id, run_type, ingestion_run_id,
            started_at, observed_at, duration_seconds, status,
            is_slow, slow_threshold_seconds,
            files_discovered, files_processed, files_failed,
            rows_discovered, rows_loaded, rows_rejected,
            schema_error_count, schema_warning_count,
            ingestion_dq_fail_count, ingestion_dq_warning_count,
            dbt_freshness_warning_count, dbt_blocking_error_count,
            dbt_warning_count, failed_task_count, blocked_task_count,
            task_states, dbt_summary, details
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s,
            %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (dag_id, dag_run_id) DO UPDATE SET
            observed_at = EXCLUDED.observed_at,
            duration_seconds = EXCLUDED.duration_seconds,
            status = EXCLUDED.status,
            is_slow = EXCLUDED.is_slow,
            slow_threshold_seconds = EXCLUDED.slow_threshold_seconds,
            files_discovered = EXCLUDED.files_discovered,
            files_processed = EXCLUDED.files_processed,
            files_failed = EXCLUDED.files_failed,
            rows_discovered = EXCLUDED.rows_discovered,
            rows_loaded = EXCLUDED.rows_loaded,
            rows_rejected = EXCLUDED.rows_rejected,
            schema_error_count = EXCLUDED.schema_error_count,
            schema_warning_count = EXCLUDED.schema_warning_count,
            ingestion_dq_fail_count = EXCLUDED.ingestion_dq_fail_count,
            ingestion_dq_warning_count = EXCLUDED.ingestion_dq_warning_count,
            dbt_freshness_warning_count = EXCLUDED.dbt_freshness_warning_count,
            dbt_blocking_error_count = EXCLUDED.dbt_blocking_error_count,
            dbt_warning_count = EXCLUDED.dbt_warning_count,
            failed_task_count = EXCLUDED.failed_task_count,
            blocked_task_count = EXCLUDED.blocked_task_count,
            task_states = EXCLUDED.task_states,
            dbt_summary = EXCLUDED.dbt_summary,
            details = EXCLUDED.details
        RETURNING monitoring_run_id;
    """

    values = (
        snapshot.dag_id,
        snapshot.dag_run_id,
        snapshot.run_type,
        snapshot.ingestion_run_id,
        snapshot.started_at,
        snapshot.observed_at,
        snapshot.duration_seconds,
        snapshot.status,
        snapshot.is_slow,
        snapshot.slow_threshold_seconds,
        snapshot.ingestion.files_discovered,
        snapshot.ingestion.files_processed,
        snapshot.ingestion.files_failed,
        snapshot.ingestion.rows_discovered,
        snapshot.ingestion.rows_loaded,
        snapshot.ingestion.rows_rejected,
        snapshot.ingestion.schema_error_count,
        snapshot.ingestion.schema_warning_count,
        snapshot.ingestion.dq_fail_count,
        snapshot.ingestion.dq_warning_count,
        snapshot.dbt_freshness_warning_count,
        snapshot.dbt_blocking_error_count,
        snapshot.dbt_warning_count,
        snapshot.failed_task_count,
        snapshot.blocked_task_count,
        Json(dict(snapshot.task_states)),
        Json(dict(snapshot.dbt_summary)),
        Json(dict(snapshot.details)),
    )

    with connection.cursor() as cursor:
        cursor.execute(query, values)
        row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Monitoring upsert returned no monitoring_run_id")
    return int(row[0])


def record_pipeline_alerts(
    connection: PgConnection,
    *,
    monitoring_run_id: int,
    snapshot: PipelineMonitoringSnapshot,
    alerts: tuple[PipelineAlert, ...],
) -> tuple[int, ...]:
    if not alerts:
        return ()

    query = """
        INSERT INTO audit.pipeline_alerts (
            monitoring_run_id, dag_id, dag_run_id, ingestion_run_id,
            alert_type, severity, message,
            external_notification_requested, details
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (monitoring_run_id, alert_type) DO UPDATE SET
            severity = EXCLUDED.severity,
            message = EXCLUDED.message,
            external_notification_requested = EXCLUDED.external_notification_requested,
            details = EXCLUDED.details
        RETURNING pipeline_alert_id;
    """

    ids: list[int] = []
    with connection.cursor() as cursor:
        for alert in alerts:
            cursor.execute(
                query,
                (
                    monitoring_run_id,
                    snapshot.dag_id,
                    snapshot.dag_run_id,
                    snapshot.ingestion_run_id,
                    alert.alert_type,
                    alert.severity,
                    alert.message,
                    alert.external_notification_requested,
                    Json(dict(alert.details)),
                ),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Alert upsert returned no pipeline_alert_id")
            ids.append(int(row[0]))

    return tuple(ids)


def update_alert_delivery(
    connection: PgConnection,
    *,
    pipeline_alert_id: int,
    status: DeliveryStatus,
    error: str | None = None,
) -> None:
    if status not in {"recorded", "not_configured", "sent", "failed"}:
        raise ValueError(f"Unsupported delivery status: {status}")

    query = """
        UPDATE audit.pipeline_alerts
        SET delivery_status = %s,
            delivery_attempted_at = CASE
                WHEN %s IN ('sent', 'failed') THEN CURRENT_TIMESTAMP
                ELSE delivery_attempted_at
            END,
            delivery_error = %s
        WHERE pipeline_alert_id = %s;
    """
    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (status, status, error, pipeline_alert_id),
        )
        if cursor.rowcount != 1:
            raise RuntimeError(
                "Alert delivery update affected unexpected rows: "
                f"pipeline_alert_id={pipeline_alert_id}, rowcount={cursor.rowcount}"
            )


def send_webhook_alert(
    *,
    webhook_url: str | None,
    snapshot: PipelineMonitoringSnapshot,
    alert: PipelineAlert,
    timeout_seconds: float = 5.0,
) -> WebhookDeliveryResult:
    if not alert.external_notification_requested:
        return WebhookDeliveryResult(status="recorded")
    if not webhook_url:
        return WebhookDeliveryResult(status="not_configured")

    payload = {
        "dag_id": snapshot.dag_id,
        "dag_run_id": snapshot.dag_run_id,
        "run_type": snapshot.run_type,
        "status": snapshot.status,
        "duration_seconds": round(snapshot.duration_seconds, 3),
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "message": alert.message,
        "details": dict(alert.details),
    }
    request = Request(
        webhook_url,
        data=json.dumps(payload, sort_keys=True).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            status_code = int(response.status)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return WebhookDeliveryResult(status="failed", error=str(exc))

    if 200 <= status_code < 300:
        return WebhookDeliveryResult(status="sent")
    return WebhookDeliveryResult(
        status="failed",
        error=f"Webhook returned HTTP {status_code}",
    )
