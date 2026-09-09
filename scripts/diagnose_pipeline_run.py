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
from ecommerce_pipeline.reliability.incident_diagnostics import (  # noqa: E402
    diagnostics_to_dict,
    load_pipeline_run_diagnostics,
)


def _connection(*, database: str):
    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=database,
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )
    connection.set_session(readonly=True, autocommit=True)
    return connection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only Airflow + pipeline incident diagnostics."
    )
    parser.add_argument("--dag-run-id", required=True)
    parser.add_argument("--dag-id", default="ecommerce_ingestion")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    app_db = os.getenv("POSTGRES_DB", "ecommerce")
    airflow_db = os.getenv("AIRFLOW_METADATA_DB", "airflow")
    application = _connection(database=app_db)
    airflow = _connection(database=airflow_db)
    try:
        diagnostics = load_pipeline_run_diagnostics(
            application_connection=application,
            airflow_connection=airflow,
            dag_id=args.dag_id,
            dag_run_id=args.dag_run_id,
        )
    finally:
        application.close()
        airflow.close()

    payload = diagnostics_to_dict(diagnostics)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"DagRun: {payload['dag_run_id']}")
    print(f"State: {payload['run_state']} ({payload['run_type']})")
    print(f"Duration: {payload['duration_seconds']}s")
    print(
        "Monitoring: "
        f"{payload['monitoring_status']} slow={payload['monitoring_is_slow']}"
    )
    print(
        "Tasks: "
        + ", ".join(
            f"{task['task_id']}={task['state']}"
            f"(try {task['try_number']}/{task['max_tries']})"
            for task in payload["tasks"]
        )
    )
    if payload["alerts"]:
        print(
            "Alerts: "
            + ", ".join(
                f"{alert['alert_type']}:{alert['severity']}"
                f" resolved={alert['resolved']}"
                for alert in payload["alerts"]
            )
        )
    else:
        print("Alerts: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
