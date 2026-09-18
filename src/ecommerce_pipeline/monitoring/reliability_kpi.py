"""Reliability KPI computation for the ecommerce data platform.

Computes pipeline reliability metrics (success rate, runtime percentiles,
incident counts, and mean time to recover) from the audit tables written by
the pipeline monitoring layer:

- ``audit.pipeline_monitoring_runs`` — one row per monitored DAG run.
- ``audit.pipeline_alerts`` — one row per fired alert/incident, with an
  incident lifecycle (``resolved`` / ``resolved_at``).

The module is split into two layers:

- Pure computation functions that operate on in-memory records
  (:class:`PipelineRunRecord`, :class:`IncidentRecord`) and are unit-testable
  without a database.
- Read-only database loading functions that translate audit rows into those
  records.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from math import ceil, floor
from typing import Any

from psycopg2.extensions import connection as PgConnection

DEFAULT_WINDOW_DAYS = 30


@dataclass(frozen=True)
class PipelineRunRecord:
    """Minimal view of one monitored pipeline run used for KPI computation."""

    dag_id: str
    dag_run_id: str
    status: str
    duration_seconds: float
    started_at: datetime


@dataclass(frozen=True)
class IncidentRecord:
    """Minimal view of one pipeline alert/incident used for KPI computation."""

    pipeline_alert_id: int
    alert_type: str
    severity: str
    fired_at: datetime
    resolved: bool
    recovered_at: datetime | None


@dataclass(frozen=True)
class ReliabilityKpiReport:
    """Aggregated reliability KPIs over a sliding window of days."""

    window_days: int
    total_runs: int
    successful_runs: int
    failed_runs: int
    success_rate_pct: float
    p50_runtime_seconds: float | None
    p95_runtime_seconds: float | None
    total_incidents: int
    open_incidents: int
    recurring_incidents: int
    mean_time_to_recover_seconds: float | None
    retry_recovered_count: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report to a plain dict (JSON-safe primitives)."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Pure computation functions (no database access)
# ---------------------------------------------------------------------------


def compute_success_rate(successful_runs: int, total_runs: int) -> float:
    """Return success rate in percent; 0.0 when there are no runs."""
    if successful_runs < 0 or total_runs < 0:
        raise ValueError("run counts must be >= 0")
    if successful_runs > total_runs:
        raise ValueError("successful_runs cannot exceed total_runs")
    if total_runs == 0:
        return 0.0
    return (successful_runs / total_runs) * 100.0


def compute_percentile(values: Sequence[float], percentile: float) -> float | None:
    """Return the percentile of ``values`` using linear interpolation.

    Method: linear interpolation between closest ranks (the same convention
    as numpy's default ``method='linear'``). The percentile position is
    ``p/100 * (n - 1)`` over the sorted sample; when it falls between two
    ranks, the result is interpolated between the neighbouring values.
    Returns ``None`` for an empty sample so callers can render "no data"
    instead of a misleading number.
    """
    if not 0.0 <= percentile <= 100.0:
        raise ValueError(f"percentile must be in [0, 100], got {percentile}")
    data = sorted(float(v) for v in values)
    if not data:
        return None
    if len(data) == 1:
        return data[0]
    rank = (percentile / 100.0) * (len(data) - 1)
    lower = floor(rank)
    upper = ceil(rank)
    if lower == upper:
        return data[lower]
    fraction = rank - lower
    return data[lower] + (data[upper] - data[lower]) * fraction


def compute_mttr(incidents: Sequence[IncidentRecord]) -> float | None:
    """Return mean time to recover in seconds across resolved incidents.

    Recovery time per incident is ``recovered_at - fired_at`` (the alert
    lifecycle pair). Unresolved incidents are excluded. Returns ``None``
    when no incident has been recovered yet.
    """
    recovery_times: list[float] = []
    for incident in incidents:
        if not incident.resolved or incident.recovered_at is None:
            continue
        delta = (incident.recovered_at - incident.fired_at).total_seconds()
        if delta < 0:
            raise ValueError(
                f"recovered_at precedes fired_at for pipeline_alert_id={incident.pipeline_alert_id}"
            )
        recovery_times.append(delta)
    if not recovery_times:
        return None
    return sum(recovery_times) / len(recovery_times)


def count_recurring_incidents(incidents: Sequence[IncidentRecord]) -> int:
    """Count incidents whose ``alert_type`` fired more than once in the window.

    A recurring incident signals a repeated failure mode rather than a
    one-off event, so every incident belonging to a repeated alert_type is
    counted (e.g. 3 ``pipeline_failure`` alerts contribute 3, not 1).
    """
    type_counts: dict[str, int] = {}
    for incident in incidents:
        type_counts[incident.alert_type] = type_counts.get(incident.alert_type, 0) + 1
    return sum(count for count in type_counts.values() if count > 1)


def count_retry_recovered(runs: Sequence[PipelineRunRecord]) -> int:
    """Count failed runs that were later recovered by a successful run.

    A failed run counts as "retry recovered" when the same ``dag_id`` has a
    successful run that started strictly after the failure started. This
    approximates automated/manual retry recovery from run history alone.
    """
    latest_success_by_dag: dict[str, datetime] = {}
    for run in runs:
        if run.status != "success":
            continue
        current = latest_success_by_dag.get(run.dag_id)
        if current is None or run.started_at > current:
            latest_success_by_dag[run.dag_id] = run.started_at

    recovered = 0
    for run in runs:
        if run.status != "failed":
            continue
        recovered_at = latest_success_by_dag.get(run.dag_id)
        if recovered_at is not None and recovered_at > run.started_at:
            recovered += 1
    return recovered


def build_kpi_report(
    *,
    window_days: int,
    runs: Sequence[PipelineRunRecord],
    incidents: Sequence[IncidentRecord],
) -> ReliabilityKpiReport:
    """Build a :class:`ReliabilityKpiReport` from in-memory records.

    Safe on empty input: with no runs the rate is 0.0 and the runtime
    percentiles are ``None``; with no resolved incidents MTTR is ``None``.
    """
    if window_days <= 0:
        raise ValueError("window_days must be > 0")

    total_runs = len(runs)
    successful_runs = sum(run.status == "success" for run in runs)
    failed_runs = sum(run.status == "failed" for run in runs)
    durations = [run.duration_seconds for run in runs]

    return ReliabilityKpiReport(
        window_days=window_days,
        total_runs=total_runs,
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        success_rate_pct=compute_success_rate(successful_runs, total_runs),
        p50_runtime_seconds=compute_percentile(durations, 50.0),
        p95_runtime_seconds=compute_percentile(durations, 95.0),
        total_incidents=len(incidents),
        open_incidents=sum(not incident.resolved for incident in incidents),
        recurring_incidents=count_recurring_incidents(incidents),
        mean_time_to_recover_seconds=compute_mttr(incidents),
        retry_recovered_count=count_retry_recovered(runs),
    )


# ---------------------------------------------------------------------------
# Database loading functions (read-only)
# ---------------------------------------------------------------------------


def load_pipeline_runs(
    connection: PgConnection,
    window_days: int,
) -> list[PipelineRunRecord]:
    """Load monitored pipeline runs observed within the last ``window_days``."""
    if window_days <= 0:
        raise ValueError("window_days must be > 0")

    query = """
        SELECT
            dag_id,
            dag_run_id,
            status,
            duration_seconds,
            started_at
        FROM audit.pipeline_monitoring_runs
        WHERE observed_at >= CURRENT_TIMESTAMP - make_interval(days => %s)
        ORDER BY observed_at;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (window_days,))
        rows = cursor.fetchall()

    return [
        PipelineRunRecord(
            dag_id=str(row[0]),
            dag_run_id=str(row[1]),
            status=str(row[2]),
            duration_seconds=float(row[3]),
            started_at=row[4],
        )
        for row in rows
    ]


def load_incidents(
    connection: PgConnection,
    window_days: int,
) -> list[IncidentRecord]:
    """Load pipeline alerts/incidents fired within the last ``window_days``."""
    if window_days <= 0:
        raise ValueError("window_days must be > 0")

    query = """
        SELECT
            pipeline_alert_id,
            alert_type,
            severity,
            created_at,
            resolved,
            resolved_at
        FROM audit.pipeline_alerts
        WHERE created_at >= CURRENT_TIMESTAMP - make_interval(days => %s)
        ORDER BY created_at;
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (window_days,))
        rows = cursor.fetchall()

    return [
        IncidentRecord(
            pipeline_alert_id=int(row[0]),
            alert_type=str(row[1]),
            severity=str(row[2]),
            fired_at=row[3],
            resolved=bool(row[4]),
            recovered_at=row[5],
        )
        for row in rows
    ]
