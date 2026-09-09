import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_DEFAULT_DBT_PROJECT_DIR = Path("/opt/airflow/dbt")
_ALLOWED_BACKFILL_VARS = {"backfill_start", "backfill_end"}


def resolve_backfill_vars(
    run_type: object,
    data_interval_start: datetime | None,
    data_interval_end: datetime | None,
    *,
    business_timezone: str = "Asia/Bangkok",
) -> dict[str, str]:
    normalized = getattr(run_type, "value", run_type)
    if normalized != "backfill":
        return {}

    if data_interval_start is None or data_interval_end is None:
        raise RuntimeError("Backfill run requires a complete Airflow data interval")
    if data_interval_start >= data_interval_end:
        raise RuntimeError("Backfill data interval must have start < end")

    timezone = ZoneInfo(business_timezone)
    local_start = data_interval_start.astimezone(timezone)
    local_end = data_interval_end.astimezone(timezone)

    return {
        "backfill_start": local_start.date().isoformat(),
        "backfill_end": local_end.date().isoformat(),
    }


def build_dbt_command(
    arguments: Sequence[str],
    *,
    variables: Mapping[str, str] | None = None,
    project_dir: Path | None = None,
    profiles_dir: Path | None = None,
) -> list[str]:
    project = project_dir or Path(
        os.getenv("DBT_PROJECT_DIR", str(_DEFAULT_DBT_PROJECT_DIR))
    )
    profiles = profiles_dir or Path(
        os.getenv("DBT_PROFILES_DIR", str(project))
    )

    command = [
        os.getenv("DBT_EXECUTABLE", "dbt"),
        *arguments,
        "--project-dir",
        str(project),
        "--profiles-dir",
        str(profiles),
    ]

    if variables:
        unexpected = set(variables) - _ALLOWED_BACKFILL_VARS
        if unexpected:
            raise ValueError(f"Unsupported dbt variables: {sorted(unexpected)}")
        command.extend(["--vars", json.dumps(dict(variables), sort_keys=True)])

    return command


def run_dbt_command(
    arguments: Sequence[str],
    *,
    variables: Mapping[str, str] | None = None,
    timeout_seconds: int = 900,
) -> str:
    project_dir = Path(
        os.getenv("DBT_PROJECT_DIR", str(_DEFAULT_DBT_PROJECT_DIR))
    )
    command = build_dbt_command(
        arguments,
        variables=variables,
        project_dir=project_dir,
    )
    completed = subprocess.run(
        command,
        cwd=project_dir,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    output = "\n".join(
        part.strip()
        for part in (completed.stdout, completed.stderr)
        if part and part.strip()
    )
    if output:
        print(output)
    if completed.returncode != 0:
        operation = " ".join(arguments)
        raise RuntimeError(
            f"dbt command failed: operation={operation!r}, "
            f"exit_code={completed.returncode}"
        )
    return output
