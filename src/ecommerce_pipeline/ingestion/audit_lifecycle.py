from dataclasses import dataclass
from typing import Literal

from psycopg2.extensions import connection as PgConnection

FileStatus = Literal[
    "discovered",
    "processing",
    "success",
    "failed",
    "skipped_duplicate",
    "rejected",
]


@dataclass(frozen=True)
class FileAuditState:
    ingestion_file_id: int
    status: FileStatus
    rows_discovered: int
    rows_loaded: int
    rows_rejected: int
    error_message: str | None


def _validate_counts(
    *,
    rows_discovered: int,
    rows_loaded: int,
    rows_rejected: int,
) -> None:
    if rows_discovered < 0:
        raise ValueError("rows_discovered must be >= 0")
    if rows_loaded < 0:
        raise ValueError("rows_loaded must be >= 0")
    if rows_rejected < 0:
        raise ValueError("rows_rejected must be >= 0")


def _row_to_state(row: tuple[object, ...]) -> FileAuditState:
    return FileAuditState(
        ingestion_file_id=row[0],
        status=row[1],
        rows_discovered=row[2],
        rows_loaded=row[3],
        rows_rejected=row[4],
        error_message=row[5],
    )


def mark_file_processing(
    connection: PgConnection,
    *,
    ingestion_file_id: int,
    rows_discovered: int = 0,
) -> FileAuditState:
    if rows_discovered < 0:
        raise ValueError("rows_discovered must be >= 0")

    query = """
        UPDATE audit.ingestion_files
        SET
            status = 'processing',
            processing_started_at = CURRENT_TIMESTAMP,
            processing_finished_at = NULL,
            rows_discovered = %s,
            error_message = NULL
        WHERE ingestion_file_id = %s
        RETURNING
            ingestion_file_id,
            status,
            rows_discovered,
            rows_loaded,
            rows_rejected,
            error_message;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (rows_discovered, ingestion_file_id))
        row = cursor.fetchone()

    if row is None:
        raise KeyError(f"Unknown ingestion_file_id: {ingestion_file_id}")

    return _row_to_state(row)


def mark_file_success(
    connection: PgConnection,
    *,
    ingestion_file_id: int,
    rows_discovered: int,
    rows_loaded: int,
    rows_rejected: int = 0,
) -> FileAuditState:
    _validate_counts(
        rows_discovered=rows_discovered,
        rows_loaded=rows_loaded,
        rows_rejected=rows_rejected,
    )

    query = """
        UPDATE audit.ingestion_files
        SET
            status = 'success',
            processing_finished_at = CURRENT_TIMESTAMP,
            rows_discovered = %s,
            rows_loaded = %s,
            rows_rejected = %s,
            error_message = NULL
        WHERE ingestion_file_id = %s
        RETURNING
            ingestion_file_id,
            status,
            rows_discovered,
            rows_loaded,
            rows_rejected,
            error_message;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                rows_discovered,
                rows_loaded,
                rows_rejected,
                ingestion_file_id,
            ),
        )
        row = cursor.fetchone()

    if row is None:
        raise KeyError(f"Unknown ingestion_file_id: {ingestion_file_id}")

    return _row_to_state(row)


def mark_file_failed(
    connection: PgConnection,
    *,
    ingestion_file_id: int,
    rows_discovered: int,
    rows_loaded: int,
    rows_rejected: int,
    error_message: str,
) -> FileAuditState:
    _validate_counts(
        rows_discovered=rows_discovered,
        rows_loaded=rows_loaded,
        rows_rejected=rows_rejected,
    )

    if not error_message.strip():
        raise ValueError("error_message must not be blank")

    query = """
        UPDATE audit.ingestion_files
        SET
            status = 'failed',
            processing_finished_at = CURRENT_TIMESTAMP,
            rows_discovered = %s,
            rows_loaded = %s,
            rows_rejected = %s,
            error_message = %s
        WHERE ingestion_file_id = %s
        RETURNING
            ingestion_file_id,
            status,
            rows_discovered,
            rows_loaded,
            rows_rejected,
            error_message;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                rows_discovered,
                rows_loaded,
                rows_rejected,
                error_message,
                ingestion_file_id,
            ),
        )
        row = cursor.fetchone()

    if row is None:
        raise KeyError(f"Unknown ingestion_file_id: {ingestion_file_id}")

    return _row_to_state(row)
