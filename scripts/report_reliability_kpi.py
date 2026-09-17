"""Print a Reliability KPI report (success rate / runtime percentiles / MTTR).

Read-only: opens a read-only transaction and issues SELECT queries against
the audit monitoring tables only.

Usage:
    python scripts/report_reliability_kpi.py [--window-days 30] [--format text|json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecommerce_pipeline.ingestion.file_registry import connect_postgres  # noqa: E402
from ecommerce_pipeline.monitoring.reliability_kpi import (  # noqa: E402
    DEFAULT_WINDOW_DAYS,
    ReliabilityKpiReport,
    build_kpi_report,
    load_incidents,
    load_pipeline_runs,
)


def _format_seconds_compact(seconds: float | None) -> str:
    """Render seconds as a compact duration, e.g. ``61s`` or ``7m 42s``."""
    if seconds is None:
        return "-"
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _format_runtime_seconds(seconds: float | None) -> str:
    """Render a runtime percentile as whole seconds, e.g. ``61s``."""
    if seconds is None:
        return "-"
    return f"{int(round(seconds))}s"


def format_text(report: ReliabilityKpiReport) -> str:
    """Render the KPI report as an aligned plain-text table."""
    lines = [
        f"Reliability KPI (last {report.window_days} days)",
        f"{'Pipeline runs':<18}{report.total_runs:>6}",
        f"{'Successful':<18}{report.successful_runs:>6}",
        f"{'Failed':<18}{report.failed_runs:>6}",
        f"{'Success rate':<18}{report.success_rate_pct:>5.1f}%",
        f"{'p50 runtime':<18}{_format_runtime_seconds(report.p50_runtime_seconds):>6}",
        f"{'p95 runtime':<18}{_format_runtime_seconds(report.p95_runtime_seconds):>6}",
        f"{'Incidents':<18}{report.total_incidents:>6}",
        f"{'Open incidents':<18}{report.open_incidents:>6}",
        f"{'Recurring':<18}{report.recurring_incidents:>6}",
        f"{'Mean recovery':<18}{_format_seconds_compact(report.mean_time_to_recover_seconds):>6}",
        f"{'Retry recovered':<18}{report.retry_recovered_count:>6}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report pipeline reliability KPIs from audit monitoring tables."
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help=f"Lookback window in days (default: {DEFAULT_WINDOW_DAYS}).",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    args = parser.parse_args(argv)

    if args.window_days <= 0:
        parser.error("--window-days must be > 0")

    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.environ["POSTGRES_PASSWORD"],
        role=os.getenv("POSTGRES_ROLE", "ecommerce_ingest_writer"),
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
        runs = load_pipeline_runs(connection, args.window_days)
        incidents = load_incidents(connection, args.window_days)
    finally:
        connection.rollback()
        connection.close()

    report = build_kpi_report(
        window_days=args.window_days,
        runs=runs,
        incidents=incidents,
    )

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
