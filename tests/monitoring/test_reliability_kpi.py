"""Unit tests for ecommerce_pipeline.monitoring.reliability_kpi (no DB)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from ecommerce_pipeline.monitoring.reliability_kpi import (
    IncidentRecord,
    PipelineRunRecord,
    ReliabilityKpiReport,
    build_kpi_report,
    compute_mttr,
    compute_percentile,
    compute_success_rate,
    count_recurring_incidents,
    count_retry_recovered,
)

UTC = UTC
BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _run(
    dag_id: str = "ingest_orders",
    status: str = "success",
    duration: float = 60.0,
    started_at: datetime = BASE,
    dag_run_id: str | None = None,
) -> PipelineRunRecord:
    return PipelineRunRecord(
        dag_id=dag_id,
        dag_run_id=dag_run_id or f"{dag_id}__{started_at.isoformat()}",
        status=status,
        duration_seconds=duration,
        started_at=started_at,
    )


def _incident(
    pipeline_alert_id: int = 1,
    alert_type: str = "pipeline_failure",
    fired_at: datetime = BASE,
    resolved: bool = True,
    recovery_seconds: float = 300.0,
) -> IncidentRecord:
    return IncidentRecord(
        pipeline_alert_id=pipeline_alert_id,
        alert_type=alert_type,
        severity="error",
        fired_at=fired_at,
        resolved=resolved,
        recovered_at=(fired_at + timedelta(seconds=recovery_seconds) if resolved else None),
    )


# ---------------------------------------------------------------------------
# compute_success_rate
# ---------------------------------------------------------------------------


def test_success_rate_normal() -> None:
    assert compute_success_rate(29, 30) == pytest.approx(96.666666, rel=1e-4)


def test_success_rate_all_successful() -> None:
    assert compute_success_rate(10, 10) == pytest.approx(100.0)


def test_success_rate_zero_runs_is_safe() -> None:
    assert compute_success_rate(0, 0) == 0.0


def test_success_rate_rejects_inconsistent_counts() -> None:
    with pytest.raises(ValueError):
        compute_success_rate(5, 4)


# ---------------------------------------------------------------------------
# compute_percentile (linear interpolation)
# ---------------------------------------------------------------------------


def test_percentile_odd_sample() -> None:
    values = [90.0, 10.0, 50.0, 30.0, 70.0]
    assert compute_percentile(values, 50.0) == pytest.approx(50.0)
    assert compute_percentile(values, 95.0) == pytest.approx(86.0)


def test_percentile_even_sample() -> None:
    values = [40.0, 10.0, 30.0, 20.0]
    assert compute_percentile(values, 50.0) == pytest.approx(25.0)
    assert compute_percentile(values, 95.0) == pytest.approx(38.5)


def test_percentile_empty_returns_none() -> None:
    assert compute_percentile([], 50.0) is None
    assert compute_percentile([], 95.0) is None


def test_percentile_single_value() -> None:
    assert compute_percentile([42.0], 95.0) == pytest.approx(42.0)


def test_percentile_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        compute_percentile([1.0], 101.0)


# ---------------------------------------------------------------------------
# compute_mttr
# ---------------------------------------------------------------------------


def test_mttr_from_incident_pairs() -> None:
    incidents = [
        _incident(pipeline_alert_id=1, recovery_seconds=300.0),
        _incident(pipeline_alert_id=2, recovery_seconds=624.0),
    ]
    assert compute_mttr(incidents) == pytest.approx(462.0)


def test_mttr_ignores_unresolved_incidents() -> None:
    incidents = [
        _incident(pipeline_alert_id=1, recovery_seconds=120.0),
        _incident(pipeline_alert_id=2, resolved=False),
    ]
    assert compute_mttr(incidents) == pytest.approx(120.0)


def test_mttr_none_when_no_incidents() -> None:
    assert compute_mttr([]) is None


def test_mttr_none_when_nothing_recovered() -> None:
    assert compute_mttr([_incident(resolved=False)]) is None


# ---------------------------------------------------------------------------
# count_recurring_incidents / count_retry_recovered
# ---------------------------------------------------------------------------


def test_recurring_detection() -> None:
    incidents = [
        _incident(pipeline_alert_id=1, alert_type="pipeline_failure"),
        _incident(pipeline_alert_id=2, alert_type="pipeline_failure"),
        _incident(pipeline_alert_id=3, alert_type="slow_pipeline"),
    ]
    assert count_recurring_incidents(incidents) == 2


def test_recurring_none_when_all_unique() -> None:
    incidents = [
        _incident(pipeline_alert_id=1, alert_type="pipeline_failure"),
        _incident(pipeline_alert_id=2, alert_type="slow_pipeline"),
    ]
    assert count_recurring_incidents(incidents) == 0
    assert count_recurring_incidents([]) == 0


def test_retry_recovered_counts_failed_then_success() -> None:
    runs = [
        _run(status="failed", started_at=BASE),
        _run(status="failed", started_at=BASE + timedelta(hours=1)),
        _run(status="success", started_at=BASE + timedelta(hours=2)),
    ]
    assert count_retry_recovered(runs) == 2


def test_retry_recovered_ignores_unrecovered_failure() -> None:
    runs = [
        _run(status="success", started_at=BASE),
        _run(status="failed", started_at=BASE + timedelta(hours=1)),
        _run(
            dag_id="other_dag",
            status="success",
            started_at=BASE + timedelta(hours=2),
        ),
    ]
    assert count_retry_recovered(runs) == 0


# ---------------------------------------------------------------------------
# build_kpi_report / serialization
# ---------------------------------------------------------------------------


def test_build_kpi_report_populates_all_fields() -> None:
    runs = [
        _run(status="success", duration=60.0, started_at=BASE),
        _run(status="success", duration=62.0, started_at=BASE + timedelta(hours=1)),
        _run(status="success", duration=58.0, started_at=BASE + timedelta(hours=2)),
        _run(status="failed", duration=120.0, started_at=BASE + timedelta(hours=3)),
        _run(status="success", duration=61.0, started_at=BASE + timedelta(hours=4)),
    ]
    incidents = [
        _incident(pipeline_alert_id=1, recovery_seconds=462.0),
        _incident(pipeline_alert_id=2, alert_type="pipeline_failure", recovery_seconds=100.0),
    ]
    report = build_kpi_report(window_days=30, runs=runs, incidents=incidents)

    assert report.window_days == 30
    assert report.total_runs == 5
    assert report.successful_runs == 4
    assert report.failed_runs == 1
    assert report.success_rate_pct == pytest.approx(80.0)
    assert report.p50_runtime_seconds == pytest.approx(61.0)
    assert report.p95_runtime_seconds == pytest.approx(108.4)
    assert report.total_incidents == 2
    assert report.open_incidents == 0
    assert report.recurring_incidents == 2
    assert report.mean_time_to_recover_seconds == pytest.approx(281.0)
    assert report.retry_recovered_count == 1


def test_build_kpi_report_empty_is_safe() -> None:
    report = build_kpi_report(window_days=30, runs=[], incidents=[])
    assert report == ReliabilityKpiReport(
        window_days=30,
        total_runs=0,
        successful_runs=0,
        failed_runs=0,
        success_rate_pct=0.0,
        p50_runtime_seconds=None,
        p95_runtime_seconds=None,
        total_incidents=0,
        open_incidents=0,
        recurring_incidents=0,
        mean_time_to_recover_seconds=None,
        retry_recovered_count=0,
    )


def test_build_kpi_report_rejects_nonpositive_window() -> None:
    with pytest.raises(ValueError):
        build_kpi_report(window_days=0, runs=[], incidents=[])


def test_report_serialization_is_json_safe() -> None:
    report = build_kpi_report(
        window_days=7,
        runs=[_run()],
        incidents=[_incident(recovery_seconds=60.0)],
    )
    payload = report.to_dict()
    assert payload["window_days"] == 7
    assert payload["success_rate_pct"] == pytest.approx(100.0)
    assert payload["mean_time_to_recover_seconds"] == pytest.approx(60.0)
    # Round-trips through JSON without custom encoders.
    decoded = json.loads(json.dumps(payload))
    assert decoded == payload
