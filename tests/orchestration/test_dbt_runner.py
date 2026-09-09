from datetime import UTC, datetime
from pathlib import Path

import pytest

from ecommerce_pipeline.orchestration.dbt_runner import (
    build_dbt_command,
    resolve_backfill_vars,
)


def test_resolve_backfill_vars_from_data_interval() -> None:
    start = datetime(2026, 8, 15, tzinfo=UTC)
    end = datetime(2026, 8, 16, tzinfo=UTC)

    assert resolve_backfill_vars("backfill", start, end) == {
        "backfill_start": "2026-08-15",
        "backfill_end": "2026-08-16",
    }


def test_non_backfill_run_has_no_dbt_vars() -> None:
    assert resolve_backfill_vars("manual", None, None) == {}


def test_invalid_backfill_interval_fails() -> None:
    moment = datetime(2026, 8, 15, tzinfo=UTC)
    with pytest.raises(RuntimeError, match="start < end"):
        resolve_backfill_vars("backfill", moment, moment)


def test_build_dbt_command_has_explicit_project_and_profiles() -> None:
    command = build_dbt_command(
        ["run"],
        variables={"backfill_start": "2026-08-15", "backfill_end": "2026-08-16"},
        project_dir=Path("/opt/airflow/dbt"),
        profiles_dir=Path("/opt/airflow/dbt"),
    )

    assert command[1] == "run"
    assert command[-6] == "--project-dir"
    assert command[-5].replace("\\", "/").endswith("/opt/airflow/dbt")
    assert command[-4] == "--profiles-dir"
    assert command[-3].replace("\\", "/").endswith("/opt/airflow/dbt")
    assert command[-2] == "--vars"
    assert "backfill_start" in command[-1]


def test_build_dbt_command_rejects_unapproved_vars() -> None:
    with pytest.raises(ValueError, match="Unsupported dbt variables"):
        build_dbt_command(["run"], variables={"password": "secret"})


def test_backfill_vars_use_bangkok_business_date_at_schedule_boundary() -> None:
    start = datetime(2026, 8, 15, 19, tzinfo=UTC)
    end = datetime(2026, 8, 16, 19, tzinfo=UTC)

    assert resolve_backfill_vars("backfill", start, end) == {
        "backfill_start": "2026-08-16",
        "backfill_end": "2026-08-17",
    }
