import os
from uuid import uuid4

import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.ingestion.incremental_state import (
    get_watermark_state,
    upsert_watermark_state,
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


def _create_ingestion_run(connection) -> int:
    query = """
        INSERT INTO audit.ingestion_runs (
            pipeline_name,
            run_type,
            status
        )
        VALUES (
            'pytest_incremental_state',
            'test',
            'running'
        )
        RETURNING ingestion_run_id;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    connection.commit()
    return row[0]


def _create_ingestion_file(
    connection,
    *,
    ingestion_run_id: int,
    source_name: str,
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
            %s,
            %s,
            %s,
            %s,
            'success'
        )
        RETURNING ingestion_file_id;
    """

    file_name = f"{source_name}_{token}.csv"
    file_path = f"/pytest/{file_name}"
    file_hash = token.ljust(64, "0")[:64]

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                ingestion_run_id,
                source_name,
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
    source_name: str,
    ingestion_file_ids: list[int],
    ingestion_run_ids: list[int],
) -> None:
    connection.rollback()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM audit.source_watermarks
            WHERE source_name = %s;
            """,
            (source_name,),
        )

        for ingestion_file_id in ingestion_file_ids:
            cursor.execute(
                """
                DELETE FROM audit.ingestion_files
                WHERE ingestion_file_id = %s;
                """,
                (ingestion_file_id,),
            )

        for ingestion_run_id in ingestion_run_ids:
            cursor.execute(
                """
                DELETE FROM audit.ingestion_runs
                WHERE ingestion_run_id = %s;
                """,
                (ingestion_run_id,),
            )

    connection.commit()


def test_watermark_insert_update_and_rollback(
    postgres_connection,
) -> None:
    token = uuid4().hex
    source_name = f"pytest_incremental_{token}"

    ingestion_run_ids: list[int] = []
    ingestion_file_ids: list[int] = []

    try:
        initial_state = get_watermark_state(
            postgres_connection,
            source_name=source_name,
        )

        assert initial_state is None

        first_run_id = _create_ingestion_run(
            postgres_connection
        )
        ingestion_run_ids.append(first_run_id)

        first_file_id = _create_ingestion_file(
            postgres_connection,
            ingestion_run_id=first_run_id,
            source_name=source_name,
            token=f"{token}a",
        )
        ingestion_file_ids.append(first_file_id)

        with transaction_scope(postgres_connection):
            first_state = upsert_watermark_state(
                postgres_connection,
                source_name=source_name,
                watermark_type="file",
                watermark_value="file_001.csv",
                last_successful_run_id=first_run_id,
                last_successful_file_id=first_file_id,
            )

        assert first_state.watermark_value == "file_001.csv"

        persisted_first_state = get_watermark_state(
            postgres_connection,
            source_name=source_name,
        )

        assert persisted_first_state == first_state

        second_run_id = _create_ingestion_run(
            postgres_connection
        )
        ingestion_run_ids.append(second_run_id)

        second_file_id = _create_ingestion_file(
            postgres_connection,
            ingestion_run_id=second_run_id,
            source_name=source_name,
            token=f"{token}b",
        )
        ingestion_file_ids.append(second_file_id)

        with transaction_scope(postgres_connection):
            second_state = upsert_watermark_state(
                postgres_connection,
                source_name=source_name,
                watermark_type="file",
                watermark_value="file_002.csv",
                last_successful_run_id=second_run_id,
                last_successful_file_id=second_file_id,
            )

        assert second_state.watermark_value == "file_002.csv"

        persisted_second_state = get_watermark_state(
            postgres_connection,
            source_name=source_name,
        )

        assert persisted_second_state == second_state

        with pytest.raises(
            RuntimeError,
            match="simulated watermark failure",
        ):
            with transaction_scope(postgres_connection):
                upsert_watermark_state(
                    postgres_connection,
                    source_name=source_name,
                    watermark_type="file",
                    watermark_value="file_003.csv",
                    last_successful_run_id=second_run_id,
                    last_successful_file_id=second_file_id,
                )
                raise RuntimeError(
                    "simulated watermark failure"
                )

        state_after_rollback = get_watermark_state(
            postgres_connection,
            source_name=source_name,
        )

        assert state_after_rollback == second_state
    finally:
        _delete_test_records(
            postgres_connection,
            source_name=source_name,
            ingestion_file_ids=ingestion_file_ids,
            ingestion_run_ids=ingestion_run_ids,
        )
