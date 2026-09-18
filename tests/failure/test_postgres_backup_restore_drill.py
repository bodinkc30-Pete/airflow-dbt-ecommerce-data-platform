import os
import re
import shutil
import subprocess

import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.reliability.backup_restore import (
    evidence_to_dict,
    run_backup_restore_drill,
)

SCRATCH_DATABASE = "drill_restore_verify"


def _env() -> dict[str, object]:
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "database": os.getenv("POSTGRES_DB", "ecommerce"),
        "user": os.getenv("POSTGRES_USER", "airflow"),
        "password": os.getenv("POSTGRES_PASSWORD", "change_me"),
    }


def _binary_major_version(binary: str) -> int | None:
    """Major version of a PostgreSQL client binary, or None if unavailable."""
    path = shutil.which(binary)
    if path is None:
        return None
    result = subprocess.run(
        [path, "--version"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    match = re.search(r"(\d+)", result.stdout)
    return int(match.group(1)) if match else None


def _server_major_version(env: dict[str, object]) -> int:
    connection = connect_postgres(
        host=str(env["host"]),
        port=int(env["port"]),
        database=str(env["database"]),
        user=str(env["user"]),
        password=str(env["password"]),
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW server_version")
            version = str(cursor.fetchone()[0])
    finally:
        connection.close()
    return int(re.match(r"(\d+)", version).group(1))


@pytest.mark.skipif(
    shutil.which("pg_dump") is None or shutil.which("pg_restore") is None,
    reason="pg_dump not available",
)
def test_backup_restore_drill_produces_rpo_rto_evidence(tmp_path) -> None:
    env = _env()
    # pg_dump/pg_restore refuse to run against a newer server major (e.g. a
    # CI runner shipping client 16 against a postgres:17 service). That is a
    # tooling limitation of the environment, not drill evidence — skip it.
    server_major = _server_major_version(env)
    dump_major = _binary_major_version("pg_dump")
    restore_major = _binary_major_version("pg_restore")
    if (
        dump_major is None
        or restore_major is None
        or dump_major < server_major
        or restore_major < server_major
    ):
        pytest.skip(
            "pg_dump/pg_restore major "
            f"({dump_major}/{restore_major}) older than server major ({server_major})"
        )
    evidence = None
    try:
        evidence = run_backup_restore_drill(
            host=str(env["host"]),
            port=int(env["port"]),
            database=str(env["database"]),
            user=str(env["user"]),
            password=str(env["password"]),
            output_dir=tmp_path,
            scratch_database=SCRATCH_DATABASE,
        )

        assert evidence.verification_status == "passed"
        assert evidence.observed_recovery_seconds > 0
        assert evidence.checksum_match is True
        assert evidence.backup_file_size_bytes > 0
        assert evidence.table_count >= 1
        assert evidence.row_count_total >= 0
        assert evidence.backup_finished_at >= evidence.backup_started_at
        assert evidence.restore_finished_at >= evidence.restore_started_at

        payload = evidence_to_dict(evidence)
        for key in (
            "backup_started_at",
            "backup_finished_at",
            "restore_started_at",
            "restore_finished_at",
            "verification_status",
            "observed_recovery_seconds",
            "table_count",
            "row_count_total",
            "checksum_match",
            "backup_file_size_bytes",
        ):
            assert key in payload
    finally:
        # The scratch database must not survive the drill, even on failure.
        connection = connect_postgres(
            host=str(env["host"]),
            port=int(env["port"]),
            database=str(env["database"]),
            user=str(env["user"]),
            password=str(env["password"]),
        )
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'DROP DATABASE IF EXISTS "drill_restore_verify";'
                )
                cursor.execute(
                    "SELECT COUNT(*) FROM pg_database WHERE datname = %s;",
                    (SCRATCH_DATABASE,),
                )
                assert int(cursor.fetchone()[0]) == 0
        finally:
            connection.close()
