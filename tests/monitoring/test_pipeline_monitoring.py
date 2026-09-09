from datetime import UTC, datetime, timedelta

import pytest

from ecommerce_pipeline.monitoring.pipeline_monitoring import (
    IngestionTelemetry,
    build_pipeline_alerts,
    build_pipeline_snapshot,
    load_ingestion_telemetry,
    send_webhook_alert,
)


def _snapshot(
    *,
    task_states: dict[str, str] | None = None,
    duration_seconds: int = 60,
    ingestion: IngestionTelemetry | None = None,
    freshness_warn: int = 0,
    blocking_error: int = 0,
    dbt_warn: int = 0,
):
    started_at = datetime(2026, 9, 9, tzinfo=UTC)
    return build_pipeline_snapshot(
        dag_id="ecommerce_ingestion",
        dag_run_id="unit_run",
        run_type="manual",
        ingestion_run_id=1,
        started_at=started_at,
        observed_at=started_at + timedelta(seconds=duration_seconds),
        slow_threshold_seconds=180,
        task_states=task_states or {"task_a": "success", "task_b": "success"},
        ingestion=ingestion or IngestionTelemetry(),
        dbt_freshness_summary={"pass": 8, "warn": freshness_warn, "error": 0},
        dbt_blocking_summary={"pass": 207, "warn": 0, "error": blocking_error},
        dbt_warning_summary={"pass": 10, "warn": dbt_warn, "error": 0},
    )


def test_success_snapshot_is_not_slow_at_baseline() -> None:
    snapshot = _snapshot(duration_seconds=54)

    assert snapshot.status == "success"
    assert snapshot.is_slow is False
    assert snapshot.failed_task_count == 0
    assert snapshot.blocked_task_count == 0


def test_failure_snapshot_counts_failed_and_blocked_tasks() -> None:
    snapshot = _snapshot(
        task_states={
            "dbt_test_blocking": "failed",
            "dbt_test_warning": "upstream_failed",
        }
    )

    assert snapshot.status == "failed"
    assert snapshot.failed_task_count == 1
    assert snapshot.blocked_task_count == 1


def test_alert_policy_separates_errors_from_warning_notifications() -> None:
    snapshot = _snapshot(
        task_states={"task_a": "failed"},
        duration_seconds=240,
        ingestion=IngestionTelemetry(
            schema_error_count=1,
            dq_fail_count=1,
            dq_warning_count=2,
        ),
        freshness_warn=1,
        dbt_warn=7,
    )

    alerts = build_pipeline_alerts(snapshot, notify_warnings=False)
    by_type = {alert.alert_type: alert for alert in alerts}

    assert by_type["pipeline_failure"].external_notification_requested is True
    assert by_type["slow_pipeline"].external_notification_requested is True
    assert by_type["schema_drift"].severity == "error"
    assert by_type["data_quality_failure"].severity == "error"
    assert by_type["data_quality_warning"].external_notification_requested is False
    assert by_type["dbt_freshness_warning"].external_notification_requested is False
    assert by_type["dbt_warning"].external_notification_requested is False


def test_warning_notifications_can_be_enabled() -> None:
    snapshot = _snapshot(dbt_warn=2)
    alerts = build_pipeline_alerts(snapshot, notify_warnings=True)

    assert alerts[0].alert_type == "dbt_warning"
    assert alerts[0].external_notification_requested is True


def test_no_ingestion_run_returns_zero_telemetry() -> None:
    assert load_ingestion_telemetry(object(), None) == IngestionTelemetry()


def test_webhook_not_configured_is_non_blocking() -> None:
    snapshot = _snapshot(task_states={"task_a": "failed"})
    alert = build_pipeline_alerts(snapshot)[0]

    result = send_webhook_alert(
        webhook_url=None,
        snapshot=snapshot,
        alert=alert,
    )

    assert result.status == "not_configured"
    assert result.error is None


def test_invalid_dbt_summary_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid dbt summary count"):
        _snapshot(dbt_warn=-1)
