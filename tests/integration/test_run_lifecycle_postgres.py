import os
from uuid import uuid4

import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.ingestion.run_lifecycle import (
    create_ingestion_run,
    mark_run_failed,
    mark_run_success,
)
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


def _delete_test_runs(
    connection,
    *,
    ingestion_run_ids: list[int],
) -> None:
    connection.rollback()

    with connection.cursor() as cursor:
        for ingestion_run_id in ingestion_run_ids:
            cursor.execute(
                """
                DELETE FROM audit.ingestion_runs
                WHERE ingestion_run_id = %s;
                """,
                (ingestion_run_id,),
            )

    connection.commit()


def test_run_lifecycle_commit_paths(
    postgres_connection,
) -> None:
    token = uuid4().hex
    ingestion_run_ids: list[int] = []

    try:
        with transaction_scope(postgres_connection):
            success_run = create_ingestion_run(
                postgres_connection,
                pipeline_name=f"pytest_run_lifecycle_success_{token}",
                run_type="test",
            )

        ingestion_run_ids.append(success_run.ingestion_run_id)

        assert success_run.status == "running"
        assert success_run.finished_at is None

        with transaction_scope(postgres_connection):
            success_state = mark_run_success(
                postgres_connection,
                ingestion_run_id=success_run.ingestion_run_id,
                files_discovered=2,
                files_processed=2,
                files_failed=0,
                rows_discovered=20,
                rows_loaded=19,
                rows_rejected=1,
            )

        assert success_state.status == "success"
        assert success_state.finished_at is not None
        assert success_state.files_discovered == 2
        assert success_state.files_processed == 2
        assert success_state.files_failed == 0
        assert success_state.rows_discovered == 20
        assert success_state.rows_loaded == 19
        assert success_state.rows_rejected == 1
        assert success_state.error_message is None

        with pytest.raises(
            RuntimeError,
            match="must be running to change terminal state",
        ):
            with transaction_scope(postgres_connection):
                mark_run_failed(
                    postgres_connection,
                    ingestion_run_id=success_run.ingestion_run_id,
                    files_discovered=2,
                    files_processed=1,
                    files_failed=1,
                    rows_discovered=20,
                    rows_loaded=10,
                    rows_rejected=10,
                    error_message="should not overwrite success",
                )

        with postgres_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, error_message
                FROM audit.ingestion_runs
                WHERE ingestion_run_id = %s;
                """,
                (success_run.ingestion_run_id,),
            )
            protected_success = cursor.fetchone()

        assert protected_success == ("success", None)

        with transaction_scope(postgres_connection):
            failed_run = create_ingestion_run(
                postgres_connection,
                pipeline_name=f"pytest_run_lifecycle_failed_{token}",
                run_type="test",
            )

        ingestion_run_ids.append(failed_run.ingestion_run_id)

        with transaction_scope(postgres_connection):
            failed_state = mark_run_failed(
                postgres_connection,
                ingestion_run_id=failed_run.ingestion_run_id,
                files_discovered=2,
                files_processed=1,
                files_failed=1,
                rows_discovered=20,
                rows_loaded=10,
                rows_rejected=10,
                error_message="simulated integration failure",
            )

        assert failed_state.status == "failed"
        assert failed_state.finished_at is not None
        assert failed_state.files_failed == 1
        assert failed_state.rows_loaded == 10
        assert failed_state.rows_rejected == 10
        assert failed_state.error_message == "simulated integration failure"

        with postgres_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    ingestion_run_id,
                    status,
                    finished_at IS NOT NULL,
                    files_discovered,
                    files_processed,
                    files_failed,
                    rows_discovered,
                    rows_loaded,
                    rows_rejected,
                    error_message
                FROM audit.ingestion_runs
                WHERE ingestion_run_id IN (%s, %s)
                ORDER BY ingestion_run_id;
                """,
                (
                    success_run.ingestion_run_id,
                    failed_run.ingestion_run_id,
                ),
            )
            rows = cursor.fetchall()

        assert len(rows) == 2

        states_by_id = {row[0]: row for row in rows}

        persisted_success = states_by_id[success_run.ingestion_run_id]
        assert persisted_success[1] == "success"
        assert persisted_success[2] is True
        assert persisted_success[3:9] == (2, 2, 0, 20, 19, 1)
        assert persisted_success[9] is None

        persisted_failed = states_by_id[failed_run.ingestion_run_id]
        assert persisted_failed[1] == "failed"
        assert persisted_failed[2] is True
        assert persisted_failed[3:9] == (2, 1, 1, 20, 10, 10)
        assert persisted_failed[9] == "simulated integration failure"
    finally:
        if ingestion_run_ids:
            _delete_test_runs(
                postgres_connection,
                ingestion_run_ids=ingestion_run_ids,
            )
