import os
from uuid import uuid4

import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.ingestion.transaction import transaction_scope


def _connect():
    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )
    connection.autocommit = False
    return connection


def _insert_ingestion_run(connection, pipeline_name: str) -> int:
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
        cursor.execute(query, (pipeline_name,))
        row = cursor.fetchone()

    return row[0]


def _find_ingestion_run_id(
    connection,
    pipeline_name: str,
) -> int | None:
    query = """
        SELECT ingestion_run_id
        FROM audit.ingestion_runs
        WHERE pipeline_name = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (pipeline_name,))
        row = cursor.fetchone()

    if row is None:
        return None

    return row[0]


def _delete_ingestion_run(
    connection,
    ingestion_run_id: int,
) -> None:
    query = """
        DELETE FROM audit.ingestion_runs
        WHERE ingestion_run_id = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(query, (ingestion_run_id,))

    connection.commit()


def test_transaction_scope_commits_to_postgres() -> None:
    pipeline_name = f"pytest_transaction_commit_{uuid4().hex}"

    writer = _connect()
    verifier = _connect()

    ingestion_run_id: int | None = None

    try:
        with transaction_scope(writer):
            ingestion_run_id = _insert_ingestion_run(
                writer,
                pipeline_name,
            )

        persisted_id = _find_ingestion_run_id(
            verifier,
            pipeline_name,
        )

        assert persisted_id == ingestion_run_id
    finally:
        writer.close()

        if ingestion_run_id is not None:
            _delete_ingestion_run(
                verifier,
                ingestion_run_id,
            )

        verifier.close()


def test_transaction_scope_rolls_back_postgres_on_failure() -> None:
    pipeline_name = f"pytest_transaction_rollback_{uuid4().hex}"

    writer = _connect()
    verifier = _connect()

    try:
        with pytest.raises(
            RuntimeError,
            match="simulated postgres failure",
        ):
            with transaction_scope(writer):
                _insert_ingestion_run(
                    writer,
                    pipeline_name,
                )
                raise RuntimeError(
                    "simulated postgres failure"
                )

        persisted_id = _find_ingestion_run_id(
            verifier,
            pipeline_name,
        )

        assert persisted_id is None
    finally:
        writer.close()
        verifier.close()
