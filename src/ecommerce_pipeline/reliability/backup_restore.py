"""Backup and restore drill helpers with RPO/RTO evidence capture.

This module implements the drill-only half of backup/restore validation:
it dumps the source database with ``pg_dump`` (custom format), restores the
dump into an isolated scratch database whose name must start with
``drill_restore_``, verifies table/row counts against the source, and
returns a :class:`BackupRestoreEvidence` record with measured timings.

Safety rules:
- The scratch database name must start with ``drill_restore_`` and match a
  strict identifier pattern; anything else raises ``ValueError`` before any
  DDL runs.
- Only the scratch database is ever created or dropped.
- Passwords are passed via the ``PGPASSWORD`` environment variable, never as
  command-line arguments.
- Every subprocess call has an explicit timeout.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import psycopg2
from psycopg2.extensions import connection as PgConnection

SCRATCH_DATABASE_PREFIX = "drill_restore_"
_SCRATCH_NAME_PATTERN = re.compile(r"drill_restore_[a-z0-9_]+")
VERIFICATION_SCHEMAS = ("raw", "audit")
DEFAULT_SUBPROCESS_TIMEOUT_SECONDS = 300
DUMP_FILE_NAME = "drill_backup.dump"


@dataclass(frozen=True)
class BackupRestoreEvidence:
    """RPO/RTO evidence captured by one backup/restore drill run."""

    backup_started_at: datetime
    backup_finished_at: datetime
    restore_started_at: datetime
    restore_finished_at: datetime
    verification_status: str  # "passed" or "failed"
    observed_recovery_seconds: float
    table_count: int
    row_count_total: int
    checksum_match: bool
    backup_file_size_bytes: int


def _require_binary(name: str) -> str:
    """Resolve a client binary from PATH or raise a clear error."""
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(
            f"{name!r} binary not found on PATH; install the PostgreSQL client tools"
        )
    return path


def _validate_scratch_database_name(name: str) -> str:
    """Allow only drill-owned scratch database names."""
    if not name.startswith(SCRATCH_DATABASE_PREFIX) or not _SCRATCH_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            f"Refusing to touch database {name!r}: scratch databases must match "
            f"{SCRATCH_DATABASE_PREFIX}<identifier>"
        )
    return name


def _build_backup_command(
    *,
    host: str,
    port: int,
    database: str,
    user: str,
    dump_path: Path,
    pg_dump_path: str,
) -> list[str]:
    """Build the pg_dump argv. The password is never part of the argv."""
    return [
        pg_dump_path,
        "--format=custom",
        "--host",
        str(host),
        "--port",
        str(port),
        "--username",
        user,
        "--dbname",
        database,
        "--file",
        str(dump_path),
    ]


def _build_restore_command(
    *,
    host: str,
    port: int,
    user: str,
    target_database: str,
    source_dump: Path,
    pg_restore_path: str,
) -> list[str]:
    """Build the pg_restore argv. The password is never part of the argv."""
    return [
        pg_restore_path,
        "--host",
        str(host),
        "--port",
        str(port),
        "--username",
        user,
        "--dbname",
        target_database,
        "--no-owner",
        "--exit-on-error",
        str(source_dump),
    ]


def _run_subprocess(command: list[str], *, password: str, timeout_seconds: int) -> None:
    """Run a PostgreSQL client tool with PGPASSWORD set via the environment."""
    env = dict(os.environ)
    env["PGPASSWORD"] = password
    result = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{Path(command[0]).name} failed with exit code {result.returncode}: "
            f"{result.stderr.strip()}"
        )


def create_backup(
    *,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    output_dir: Path,
    timeout_seconds: int = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
) -> Path:
    """Dump ``database`` to ``output_dir`` in pg_dump custom format."""
    pg_dump_path = _require_binary("pg_dump")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dump_path = output_dir / DUMP_FILE_NAME
    command = _build_backup_command(
        host=host,
        port=port,
        database=database,
        user=user,
        dump_path=dump_path,
        pg_dump_path=pg_dump_path,
    )
    _run_subprocess(command, password=password, timeout_seconds=timeout_seconds)
    if not dump_path.is_file() or dump_path.stat().st_size == 0:
        raise RuntimeError(f"pg_dump did not produce a non-empty dump at {dump_path}")
    return dump_path


def _drop_database(admin_connection: PgConnection, name: str) -> None:
    """Drop a drill scratch database. Only validated names reach this point."""
    _validate_scratch_database_name(name)
    with admin_connection.cursor() as cursor:
        cursor.execute(f'DROP DATABASE IF EXISTS "{name}";')


def _create_database(admin_connection: PgConnection, name: str) -> None:
    """Create a drill scratch database. Only validated names reach this point."""
    _validate_scratch_database_name(name)
    with admin_connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE "{name}";')


def restore_to_database(
    *,
    host: str,
    port: int,
    source_dump: Path,
    target_database: str,
    user: str,
    password: str,
    timeout_seconds: int = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
) -> None:
    """Create the scratch target database and restore ``source_dump`` into it."""
    _validate_scratch_database_name(target_database)
    pg_restore_path = _require_binary("pg_restore")
    command = _build_restore_command(
        host=host,
        port=port,
        user=user,
        target_database=target_database,
        source_dump=Path(source_dump),
        pg_restore_path=pg_restore_path,
    )
    _run_subprocess(command, password=password, timeout_seconds=timeout_seconds)


def verify_restore(connection: PgConnection) -> dict[str, object]:
    """Profile the tables in the verification schemas of the connected database.

    Returns a comparable dict with the table count, total row count, and a
    per-table row-count map (the drill's lightweight checksum) for the
    ``raw`` and ``audit`` schemas.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema = ANY(%s)
              AND table_type = 'BASE TABLE'
            ORDER BY table_schema, table_name;
            """,
            (list(VERIFICATION_SCHEMAS),),
        )
        tables = [(str(schema), str(name)) for schema, name in cursor.fetchall()]

    table_row_counts: dict[str, int] = {}
    with connection.cursor() as cursor:
        for schema, name in tables:
            cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{name}";')
            row = cursor.fetchone()
            table_row_counts[f"{schema}.{name}"] = int(row[0]) if row else 0

    return {
        "table_count": len(tables),
        "row_count_total": sum(table_row_counts.values()),
        "table_row_counts": table_row_counts,
    }


def _connect(host: str, port: int, database: str, user: str, password: str) -> PgConnection:
    connection = psycopg2.connect(
        host=host,
        port=port,
        dbname=database,
        user=user,
        password=password,
    )
    connection.autocommit = True
    return connection


def run_backup_restore_drill(
    *,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    output_dir: Path,
    scratch_database: str,
    timeout_seconds: int = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
) -> BackupRestoreEvidence:
    """Run the full drill: backup -> restore to scratch DB -> verify -> cleanup.

    The scratch database is always dropped, even when any step fails.
    """
    _validate_scratch_database_name(scratch_database)
    # Fail fast when the client tools are missing before any DDL runs.
    _require_binary("pg_dump")
    _require_binary("pg_restore")

    admin_connection = _connect(host, port, database, user, password)
    try:
        backup_started_at = datetime.now(UTC)
        dump_path = create_backup(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            output_dir=output_dir,
            timeout_seconds=timeout_seconds,
        )
        backup_finished_at = datetime.now(UTC)
        backup_file_size_bytes = dump_path.stat().st_size

        source_profile = verify_restore(admin_connection)

        _drop_database(admin_connection, scratch_database)
        try:
            _create_database(admin_connection, scratch_database)

            restore_started_at = datetime.now(UTC)
            restore_to_database(
                host=host,
                port=port,
                source_dump=dump_path,
                target_database=scratch_database,
                user=user,
                password=password,
                timeout_seconds=timeout_seconds,
            )
            restore_finished_at = datetime.now(UTC)
            observed_recovery_seconds = max(
                0.0,
                (restore_finished_at - restore_started_at).total_seconds(),
            )
            if observed_recovery_seconds == 0.0:
                # Sub-second restores still count as a positive recovery time.
                observed_recovery_seconds = 1e-6

            restored_connection = _connect(host, port, scratch_database, user, password)
            try:
                restored_profile = verify_restore(restored_connection)
            finally:
                restored_connection.close()

            checksum_match = (
                restored_profile["table_row_counts"] == source_profile["table_row_counts"]
            )
            verification_status = "passed" if checksum_match else "failed"

            return BackupRestoreEvidence(
                backup_started_at=backup_started_at,
                backup_finished_at=backup_finished_at,
                restore_started_at=restore_started_at,
                restore_finished_at=restore_finished_at,
                verification_status=verification_status,
                observed_recovery_seconds=observed_recovery_seconds,
                table_count=int(restored_profile["table_count"]),
                row_count_total=int(restored_profile["row_count_total"]),
                checksum_match=checksum_match,
                backup_file_size_bytes=backup_file_size_bytes,
            )
        finally:
            _drop_database(admin_connection, scratch_database)
    finally:
        admin_connection.close()


def evidence_to_dict(evidence: BackupRestoreEvidence) -> dict[str, object]:
    """Serialize evidence to a JSON-ready dict with ISO-8601 timestamps."""
    payload = asdict(evidence)
    for field in (
        "backup_started_at",
        "backup_finished_at",
        "restore_started_at",
        "restore_finished_at",
    ):
        payload[field] = getattr(evidence, field).isoformat()
    return payload


def write_evidence_json(evidence: BackupRestoreEvidence, path: Path) -> Path:
    """Write the drill evidence as JSON and return the file path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence_to_dict(evidence), indent=2) + "\n", encoding="utf-8")
    return path
