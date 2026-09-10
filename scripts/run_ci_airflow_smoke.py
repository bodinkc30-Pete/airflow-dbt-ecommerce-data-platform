from __future__ import annotations

import argparse
import re
import subprocess
import time
from datetime import UTC, datetime

DAG_ID = "ecommerce_ingestion"
TERMINAL_STATES = {"success", "failed"}
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _run(command: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout.strip() if capture else ""


def _psql(query: str) -> str:
    return _run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "airflow",
            "-d",
            "airflow",
            "-Atc",
            query,
        ],
        capture=True,
    )


def _dag_run_state(run_id: str) -> str:
    query = (
        "SELECT COALESCE(state, '') "
        "FROM dag_run "
        f"WHERE dag_id = '{DAG_ID}' AND run_id = '{run_id}' "
        "ORDER BY id DESC LIMIT 1;"
    )
    return _psql(query)


def _task_summary(run_id: str) -> dict[str, int]:
    query = (
        "SELECT COALESCE(state, 'none'), COUNT(*) "
        "FROM task_instance "
        f"WHERE dag_id = '{DAG_ID}' AND run_id = '{run_id}' "
        "GROUP BY state ORDER BY state;"
    )
    rows = _psql(query)
    summary: dict[str, int] = {}
    for line in rows.splitlines():
        if not line:
            continue
        state, count = line.split("|", maxsplit=1)
        summary[state] = int(count)
    return summary


def _validate_run_id(run_id: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(f"Invalid Airflow dag_run id: {run_id!r}")
    return run_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Airflow CI smoke DAG to a terminal state."
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--expected-tasks", type=int, default=13)
    args = parser.parse_args()

    run_id = _validate_run_id(
        "ci_smoke_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    _run(
        [
            "docker", "compose", "exec", "-T",
            "airflow-api-server", "airflow", "dags", "unpause", DAG_ID,
        ]
    )
    _run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "airflow-api-server",
            "airflow",
            "dags",
            "trigger",
            DAG_ID,
            "--run-id",
            run_id,
        ]
    )
    print(f"dag_run={run_id}")

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        state = _dag_run_state(run_id)
        if state in TERMINAL_STATES:
            summary = _task_summary(run_id)
            print(f"state={state}")
            print(f"task_instance={summary}")
            if state == "failed":
                raise RuntimeError(f"Airflow CI smoke failed: {summary}")
            if summary != {"success": args.expected_tasks}:
                raise RuntimeError(f"Unexpected Airflow task states: {summary}")
            return 0
        time.sleep(2)

    summary = _task_summary(run_id)
    raise TimeoutError(
        f"Airflow CI smoke timeout after {args.timeout}s: task_instance={summary}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
