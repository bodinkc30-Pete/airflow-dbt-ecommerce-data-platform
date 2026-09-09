import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ecommerce_pipeline.orchestration.dbt_runner import (
    DbtCommandError,
    build_dbt_command,
    parse_dbt_command_summary,
    resolve_backfill_vars,
    run_dbt_command,
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


def test_parse_dbt_test_summary() -> None:
    output = "Done. PASS=250 WARN=7 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=257"

    assert parse_dbt_command_summary(output) == {
        "pass": 250,
        "warn": 7,
        "error": 0,
        "skip": 0,
        "total": 257,
    }


def test_parse_dbt_freshness_summary() -> None:
    output = "\n".join(
        [
            "1 of 3 PASS freshness of raw.orders [PASS]",
            "2 of 3 WARN freshness of raw.shop_daily [WARN]",
            "3 of 3 PASS freshness of raw.products [PASS]",
            "Done.",
        ]
    )

    assert parse_dbt_command_summary(output) == {
        "pass": 2,
        "warn": 1,
        "error": 0,
        "skip": 0,
        "total": 3,
    }


def test_failed_dbt_command_preserves_summary_output(monkeypatch, tmp_path: Path) -> None:
    output = "Done. PASS=205 WARN=0 ERROR=2 SKIP=0 NO-OP=0 REUSED=0 TOTAL=207"

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=1, stdout=output, stderr="")

    monkeypatch.setenv("DBT_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(
        "ecommerce_pipeline.orchestration.dbt_runner.subprocess.run",
        fake_run,
    )

    with pytest.raises(DbtCommandError) as exc_info:
        run_dbt_command(["test", "--exclude", "tag:dq_warning"], timeout_seconds=10)

    assert exc_info.value.exit_code == 1
    assert parse_dbt_command_summary(exc_info.value.output)["error"] == 2
