from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from psycopg2.extensions import connection as PgConnection

RunStatus = Literal[
    "running",
    "success",
    "failed",
    "partial_success",
    "cancelled",
]

RunType = Literal[
    "scheduled",
    "manual",
    "backfill",
    "reprocessing",
    "test",
]

_ALLOWED_RUN_TYPES: frozenset[str] = frozenset(
    {
        "scheduled",
        "manual",
        "backfill",
        "reprocessing",
        "test",
    }
)


@dataclass(frozen=True)
class IngestionRunState:
    ingestion_run_id: int
    pipeline_name: str
    run_type: RunType
    started_at: datetime
    finished_at: datetime | None
    status: RunStatus
    files_discovered: int
    files_processed: int
    files_failed: int
    rows_discovered: int
    rows_loaded: int
    rows_rejected: int
    error_message: str | None


def _validate_run_type(run_type: str) -> None:
    if run_type not in _ALLOWED_RUN_TYPES:
        allowed = ", ".join(sorted(_ALLOWED_RUN_TYPES))
        raise ValueError(f"run_type must be one of: {allowed}")


def _validate_counts(
    *,
    files_discovered: int,
    files_processed: int,
    files_failed: int,
    rows_discovered: int,
    rows_loaded: int,
    rows_rejected: int,
) -> None:
    counts = {
        "files_discovered": files_discovered,
        "files_processed": files_processed,
        "files_failed": files_failed,
        "rows_discovered": rows_discovered,
        "rows_loaded": rows_loaded,
        "rows_rejected": rows_rejected,
    }

    for name, value in counts.items():
        if value < 0:
            raise ValueError(f"{name} must be >= 0")


def _row_to_state(row: tuple[object, ...]) -> IngestionRunState:
    return IngestionRunState(
        ingestion_run_id=row[0],
        pipeline_name=row[1],
        run_type=row[2],
        started_at=row[3],
        finished_at=row[4],
        status=row[5],
        files_discovered=row[6],
        files_processed=row[7],
        files_failed=row[8],
        rows_discovered=row[9],
        rows_loaded=row[10],
        rows_rejected=row[11],
        error_message=row[12],
    )


def _raise_run_transition_error(
    connection: PgConnection,
    *,
    ingestion_run_id: int,
) -> None:
    query = """
        SELECT status
        FROM audit.ingestion_runs
        WHERE ingestion_run_id = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (ingestion_run_id,))
        row = cursor.fetchone()

    if row is None:
        raise KeyError(f"Unknown ingestion_run_id: {ingestion_run_id}")

    raise RuntimeError(
        f"Ingestion run {ingestion_run_id} must be running to change terminal state; "
        f"current status: {row[0]}"
    )


def create_ingestion_run(
    connection: PgConnection,
    *,
    pipeline_name: str,
    run_type: RunType = "scheduled",
) -> IngestionRunState:
    if not pipeline_name.strip():
        raise ValueError("pipeline_name must not be blank")

    _validate_run_type(run_type)

    query = """
        INSERT INTO audit.ingestion_runs (
            pipeline_name,
            run_type
        )
        VALUES (
            %s,
            %s
        )
        RETURNING
            ingestion_run_id,
            pipeline_name,
            run_type,
            started_at,
            finished_at,
            status,
            files_discovered,
            files_processed,
            files_failed,
            rows_discovered,
            rows_loaded,
            rows_rejected,
            error_message;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (pipeline_name, run_type))
        row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Failed to create ingestion run")

    return _row_to_state(row)


def mark_run_success(
    connection: PgConnection,
    *,
    ingestion_run_id: int,
    files_discovered: int,
    files_processed: int,
    files_failed: int,
    rows_discovered: int,
    rows_loaded: int,
    rows_rejected: int,
) -> IngestionRunState:
    _validate_counts(
        files_discovered=files_discovered,
        files_processed=files_processed,
        files_failed=files_failed,
        rows_discovered=rows_discovered,
        rows_loaded=rows_loaded,
        rows_rejected=rows_rejected,
    )

    query = """
        UPDATE audit.ingestion_runs
        SET
            status = 'success',
            finished_at = CURRENT_TIMESTAMP,
            files_discovered = %s,
            files_processed = %s,
            files_failed = %s,
            rows_discovered = %s,
            rows_loaded = %s,
            rows_rejected = %s,
            error_message = NULL
        WHERE ingestion_run_id = %s
          AND status = 'running'
        RETURNING
            ingestion_run_id,
            pipeline_name,
            run_type,
            started_at,
            finished_at,
            status,
            files_discovered,
            files_processed,
            files_failed,
            rows_discovered,
            rows_loaded,
            rows_rejected,
            error_message;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                files_discovered,
                files_processed,
                files_failed,
                rows_discovered,
                rows_loaded,
                rows_rejected,
                ingestion_run_id,
            ),
        )
        row = cursor.fetchone()

    if row is None:
        _raise_run_transition_error(
            connection,
            ingestion_run_id=ingestion_run_id,
        )

    return _row_to_state(row)


def mark_run_failed(
    connection: PgConnection,
    *,
    ingestion_run_id: int,
    files_discovered: int,
    files_processed: int,
    files_failed: int,
    rows_discovered: int,
    rows_loaded: int,
    rows_rejected: int,
    error_message: str,
) -> IngestionRunState:
    _validate_counts(
        files_discovered=files_discovered,
        files_processed=files_processed,
        files_failed=files_failed,
        rows_discovered=rows_discovered,
        rows_loaded=rows_loaded,
        rows_rejected=rows_rejected,
    )

    if not error_message.strip():
        raise ValueError("error_message must not be blank")

    query = """
        UPDATE audit.ingestion_runs
        SET
            status = 'failed',
            finished_at = CURRENT_TIMESTAMP,
            files_discovered = %s,
            files_processed = %s,
            files_failed = %s,
            rows_discovered = %s,
            rows_loaded = %s,
            rows_rejected = %s,
            error_message = %s
        WHERE ingestion_run_id = %s
          AND status = 'running'
        RETURNING
            ingestion_run_id,
            pipeline_name,
            run_type,
            started_at,
            finished_at,
            status,
            files_discovered,
            files_processed,
            files_failed,
            rows_discovered,
            rows_loaded,
            rows_rejected,
            error_message;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                files_discovered,
                files_processed,
                files_failed,
                rows_discovered,
                rows_loaded,
                rows_rejected,
                error_message,
                ingestion_run_id,
            ),
        )
        row = cursor.fetchone()

    if row is None:
        _raise_run_transition_error(
            connection,
            ingestion_run_id=ingestion_run_id,
        )

    return _row_to_state(row)
