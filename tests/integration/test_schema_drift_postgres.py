import os
from uuid import uuid4

import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.ingestion.schema_drift import (
    classify_schema_drift,
    record_schema_events,
)
from ecommerce_pipeline.ingestion.schema_validation import validate_schema
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
            (f"pytest_schema_drift_{token}",),
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
            'processing'
        )
        RETURNING ingestion_file_id;
    """

    file_name = f"orders_schema_drift_{token}.csv"
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
    ingestion_file_id: int,
    ingestion_run_id: int,
) -> None:
    connection.rollback()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM audit.schema_events
            WHERE ingestion_file_id = %s;
            """,
            (ingestion_file_id,),
        )
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


def _invalid_orders_validation_result():
    columns = [f"column_{index}" for index in range(65)]
    columns[0] = "Order ID"

    return validate_schema(
        source_name="orders",
        observed_columns=columns,
    )


def test_schema_events_commit_and_rollback(
    postgres_connection,
) -> None:
    token = uuid4().hex
    ingestion_run_id = _create_ingestion_run(
        postgres_connection,
        token=token,
    )
    ingestion_file_id = _create_ingestion_file(
        postgres_connection,
        ingestion_run_id=ingestion_run_id,
        token=token,
    )

    try:
        result = _invalid_orders_validation_result()
        events = classify_schema_drift(result)

        assert events
        assert any(
            event.event_type == "missing_column"
            and event.column_name == "sku_id"
            for event in events
        )

        with transaction_scope(postgres_connection):
            event_ids = record_schema_events(
                postgres_connection,
                ingestion_run_id=ingestion_run_id,
                ingestion_file_id=ingestion_file_id,
                events=events,
            )

        assert len(event_ids) == len(events)

        with postgres_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    event_type,
                    column_name,
                    expected_value,
                    observed_value,
                    severity,
                    details
                FROM audit.schema_events
                WHERE ingestion_file_id = %s
                ORDER BY schema_event_id;
                """,
                (ingestion_file_id,),
            )
            persisted_rows = cursor.fetchall()

        assert len(persisted_rows) == len(events)

        missing_rows = [
            row
            for row in persisted_rows
            if row[0] == "missing_column"
            and row[1] == "sku_id"
        ]

        assert len(missing_rows) == 1
        assert missing_rows[0][2] == "required"
        assert missing_rows[0][3] == "missing"
        assert missing_rows[0][4] == "error"
        assert (
            missing_rows[0][5]["validation_issue_code"]
            == "MISSING_REQUIRED_COLUMN"
        )

        with pytest.raises(
            RuntimeError,
            match="simulated schema event failure",
        ):
            with transaction_scope(postgres_connection):
                record_schema_events(
                    postgres_connection,
                    ingestion_run_id=ingestion_run_id,
                    ingestion_file_id=ingestion_file_id,
                    events=events,
                )
                raise RuntimeError(
                    "simulated schema event failure"
                )

        with postgres_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM audit.schema_events
                WHERE ingestion_file_id = %s;
                """,
                (ingestion_file_id,),
            )
            persisted_count_after_rollback = cursor.fetchone()[0]

        assert persisted_count_after_rollback == len(events)
    finally:
        _delete_test_records(
            postgres_connection,
            ingestion_file_id=ingestion_file_id,
            ingestion_run_id=ingestion_run_id,
        )
