"""Failure-injection drill (unit): alert delivery failure handling.

Covers the drill scenario where the webhook endpoint is unreachable, the
webhook URL violates the https:// scheme guard, or no webhook is configured.
No PostgreSQL or network listener is required: scenario A targets a closed
loopback port, which fails fast with a connection error.
"""

from datetime import UTC, datetime, timedelta

import pytest

from ecommerce_pipeline.monitoring.pipeline_monitoring import (
    IngestionTelemetry,
    PipelineAlert,
    build_pipeline_snapshot,
    send_webhook_alert,
)


def _snapshot():
    started_at = datetime(2026, 9, 9, tzinfo=UTC)
    return build_pipeline_snapshot(
        dag_id="ecommerce_ingestion",
        dag_run_id="failure_drill_run",
        run_type="manual",
        ingestion_run_id=1,
        started_at=started_at,
        observed_at=started_at + timedelta(seconds=60),
        slow_threshold_seconds=180,
        task_states={"task_a": "failed"},
        ingestion=IngestionTelemetry(),
        dbt_freshness_summary={"pass": 8, "warn": 0, "error": 0},
        dbt_blocking_summary={"pass": 207, "warn": 0, "error": 0},
        dbt_warning_summary={"pass": 10, "warn": 0, "error": 0},
    )


def _alert() -> PipelineAlert:
    return PipelineAlert(
        alert_type="pipeline_failure",
        severity="critical",
        message="failure injection drill alert",
        external_notification_requested=True,
    )


def test_unreachable_https_webhook_fails_without_raising() -> None:
    # Scenario A: https endpoint with nothing listening on the loopback port.
    result = send_webhook_alert(
        webhook_url="https://127.0.0.1:59999/hook",
        snapshot=_snapshot(),
        alert=_alert(),
        timeout_seconds=2.0,
    )

    assert result.status == "failed"
    assert result.error


@pytest.mark.parametrize(
    "webhook_url",
    [
        "http://localhost/hook",
        "file:///etc/passwd",
    ],
)
def test_non_https_webhook_url_is_rejected(webhook_url: str) -> None:
    # Scenario B: the SSRF guard must reject anything that is not https://.
    result = send_webhook_alert(
        webhook_url=webhook_url,
        snapshot=_snapshot(),
        alert=_alert(),
    )

    assert result.status == "failed"
    assert result.error is not None
    assert "https" in result.error


def test_missing_webhook_url_is_not_configured() -> None:
    # Scenario C: no webhook configured must be non-blocking.
    result = send_webhook_alert(
        webhook_url=None,
        snapshot=_snapshot(),
        alert=_alert(),
    )

    assert result.status == "not_configured"
    assert result.error is None
