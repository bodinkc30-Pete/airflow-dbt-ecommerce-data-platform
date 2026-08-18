import os
from uuid import uuid4

import pytest

from ecommerce_pipeline.ingestion.audit_lifecycle import (
    mark_file_failed,
    mark_file_processing,
    mark_file_success,
)
from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.ingestion.transaction import transaction_scope


@pytest.fixture
def postgres_connection():
    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )
    connection.autocommit = False

    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def _create_ingestion_run(connection, *, token: str) -> int:
    query = """
        INSERT INTO audit.ingestion_runs (
            pipeline_name,
            run_type,
            status
        )
        VALUES (
            %s,
            'test',
            'running'
        )
        RETURNING ingestion_run_id;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (f"pytest_audit_lifecycle_{token}",),
        )
        row = cursor.fetchone()

    connection.commit()
    return row[0]


def _create_ingestion_file(
    connection,
    *,
    ingestion_run_id: int,
    token: str,
) -> int:
    query = """
        INSERT INTO audit.ingestion_files (
            ingestion_run_id,
            source_name,
            file_name,
            file_path,
            file_hash_sha256,
            status
        )
        VALUES (
            %s,
            'orders',
            %s,
            %s,
            %s,
            'discovered'
        )
        RETURNING ingestion_file_id;
    """

    file_name = f"orders_audit_lifecycle_{token}.csv"
    file_path = f"/pytest/{file_name}"
    file_hash = token.ljust(64, "0")[:64]

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                ingestion_run_id,
                file_name,
                file_path,
                file_hash,
            ),
        )
        row = cursor.fetchone()

    connection.commit()
    return row[0]


def _delete_test_records(
    connection,
    *,
    ingestion_file_ids: list[int],
    ingestion_run_id: int,
) -> None:
    connection.rollback()

    with connection.cursor() as cursor:
        for ingestion_file_id in ingestion_file_ids:
            cursor.execute(
                """
                DELETE FROM audit.ingestion_files
                WHERE ingestion_file_id = %s;
                """,
                (ingestion_file_id,),
            )

        cursor.execute(
            """
            DELETE FROM audit.ingestion_runs
            WHERE ingestion_run_id = %s;
            """,
            (ingestion_run_id,),
        )

    connection.commit()


def test_file_audit_lifecycle_commit_paths(
    postgres_connection,
) -> None:
    token = uuid4().hex
    ingestion_run_id = _create_ingestion_run(
        postgres_connection,
        token=token,
    )

    success_file_id = _create_ingestion_file(
        postgres_connection,
        ingestion_run_id=ingestion_run_id,
        token=f"{token}a",
    )
    failed_file_id = _create_ingestion_file(
        postgres_connection,
        ingestion_run_id=ingestion_run_id,
        token=f"{token}b",
    )

    ingestion_file_ids = [
        success_file_id,
        failed_file_id,
    ]

    try:
        with transaction_scope(postgres_connection):
            processing_state = mark_file_processing(
                postgres_connection,
                ingestion_file_id=success_file_id,
                rows_discovered=10,
            )

        assert processing_state.status == "processing"
        assert processing_state.rows_discovered == 10

        with transaction_scope(postgres_connection):
            success_state = mark_file_success(
                postgres_connection,
                ingestion_file_id=success_file_id,
                rows_discovered=10,
                rows_loaded=9,
                rows_rejected=1,
            )

        assert success_state.status == "success"
        assert success_state.rows_loaded == 9
        assert success_state.rows_rejected == 1

        with transaction_scope(postgres_connection):
            mark_file_processing(
                postgres_connection,
                ingestion_file_id=failed_file_id,
                rows_discovered=8,
            )

        with transaction_scope(postgres_connection):
            failed_state = mark_file_failed(
                postgres_connection,
                ingestion_file_id=failed_file_id,
                rows_discovered=8,
                rows_loaded=3,
                rows_rejected=5,
                error_message="simulated integration failure",
            )

        assert failed_state.status == "failed"
        assert failed_state.rows_loaded == 3
        assert failed_state.rows_rejected == 5
        assert (
            failed_state.error_message
            == "simulated integration failure"
        )

        with postgres_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    ingestion_file_id,
                    status,
                    processing_started_at IS NOT NULL,
                    processing_finished_at IS NOT NULL,
                    rows_discovered,
                    rows_loaded,
                    rows_rejected,
                    error_message
                FROM audit.ingestion_files
                WHERE ingestion_file_id IN (%s, %s)
                ORDER BY ingestion_file_id;
                """,
                (
                    success_file_id,
                    failed_file_id,
                ),
            )
            rows = cursor.fetchall()

        assert len(rows) == 2

        persisted = {
            row[0]: row
            for row in rows
        }

        success_row = persisted[success_file_id]
        failed_row = persisted[failed_file_id]

        assert success_row[1] == "success"
        assert success_row[2] is True
        assert success_row[3] is True
        assert success_row[4:7] == (10, 9, 1)
        assert success_row[7] is None

        assert failed_row[1] == "failed"
        assert failed_row[2] is True
        assert failed_row[3] is True
        assert failed_row[4:7] == (8, 3, 5)
        assert failed_row[7] == "simulated integration failure"
    finally:
        _delete_test_records(
            postgres_connection,
            ingestion_file_ids=ingestion_file_ids,
            ingestion_run_id=ingestion_run_id,
        )
