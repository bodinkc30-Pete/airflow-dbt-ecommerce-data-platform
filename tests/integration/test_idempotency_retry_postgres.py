import os
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from ecommerce_pipeline.ingestion.bulk_loader import (
    LineageMetadata,
    bulk_load_source,
)
from ecommerce_pipeline.ingestion.file_registry import (
    build_file_metadata,
    connect_postgres,
    register_file,
)
from ecommerce_pipeline.ingestion.idempotency import (
    decide_file_processing,
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
            'pytest_idempotency_retry',
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


def _mark_file_status(
    connection,
    ingestion_file_id: int,
    status: str,
) -> None:
    query = """
        UPDATE audit.ingestion_files
        SET
            status = %s,
            processing_started_at = CURRENT_TIMESTAMP,
            processing_finished_at = CURRENT_TIMESTAMP
        WHERE ingestion_file_id = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                status,
                ingestion_file_id,
            ),
        )

    connection.commit()


def _count_raw_rows(
    connection,
    ingestion_file_id: int,
) -> int:
    query = """
        SELECT COUNT(*)
        FROM raw.orders
        WHERE _ingestion_file_id = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (ingestion_file_id,),
        )
        row = cursor.fetchone()

    return row[0]


def _cleanup_test_records(
    connection,
    *,
    ingestion_file_id: int | None,
    ingestion_run_id: int | None,
) -> None:
    connection.rollback()

    with connection.cursor() as cursor:
        if ingestion_file_id is not None:
            cursor.execute(
                """
                DELETE FROM raw.orders
                WHERE _ingestion_file_id = %s;
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

        if ingestion_run_id is not None:
            cursor.execute(
                """
                DELETE FROM audit.ingestion_runs
                WHERE ingestion_run_id = %s;
                """,
                (ingestion_run_id,),
            )

    connection.commit()


def test_failed_file_can_retry_without_duplicate_raw_rows(
    postgres_connection,
    tmp_path: Path,
) -> None:
    token = uuid4().hex

    source_file = tmp_path / f"orders_retry_after_failure_{token}.csv"
    source_file.write_text(
        (
            "Order ID,SKU ID\n"
            f"ORDER_RETRY_{token}_001,SKU_RETRY_{token}_001\n"
            f"ORDER_RETRY_{token}_002,SKU_RETRY_{token}_002\n"
        ),
        encoding="utf-8",
    )

    metadata = build_file_metadata(
        source_name="orders",
        file_path=source_file,
    )

    ingestion_run_id: int | None = None
    ingestion_file_id: int | None = None

    try:
        ingestion_run_id = _create_ingestion_run(
            postgres_connection
        )

        registration = register_file(
            connection=postgres_connection,
            ingestion_run_id=ingestion_run_id,
            metadata=metadata,
        )
        postgres_connection.commit()

        ingestion_file_id = registration.ingestion_file_id

        dataframe = pd.DataFrame(
            {
                "Order ID": [
                    f"ORDER_RETRY_{token}_001",
                    f"ORDER_RETRY_{token}_002",
                ],
                "SKU ID": [
                    f"SKU_RETRY_{token}_001",
                    f"SKU_RETRY_{token}_002",
                ],
            }
        )

        lineage = LineageMetadata(
            source_file=source_file.name,
            batch_id=f"batch_retry_{token}",
            file_hash=metadata.file_hash_sha256,
            pipeline_run_id=ingestion_run_id,
            ingestion_file_id=ingestion_file_id,
        )

        with pytest.raises(
            RuntimeError,
            match="simulated load failure",
        ):
            with transaction_scope(postgres_connection):
                bulk_load_source(
                    connection=postgres_connection,
                    source_name="orders",
                    dataframe=dataframe,
                    column_mapping={
                        "Order ID": "order_id",
                        "SKU ID": "sku_id",
                    },
                    lineage=lineage,
                )
                raise RuntimeError("simulated load failure")

        assert _count_raw_rows(
            postgres_connection,
            ingestion_file_id,
        ) == 0

        _mark_file_status(
            postgres_connection,
            ingestion_file_id,
            "failed",
        )

        retry_registration = register_file(
            connection=postgres_connection,
            ingestion_run_id=ingestion_run_id,
            metadata=metadata,
        )

        assert retry_registration.is_duplicate is True
        assert retry_registration.status == "failed"
        assert (
            retry_registration.ingestion_file_id
            == ingestion_file_id
        )

        retry_decision = decide_file_processing(
            retry_registration,
            current_ingestion_run_id=ingestion_run_id,
        )

        assert retry_decision.action == "process"
        assert retry_decision.reason == "retry_failed_file"
        assert retry_decision.should_process is True

        with transaction_scope(postgres_connection):
            retry_result = bulk_load_source(
                connection=postgres_connection,
                source_name="orders",
                dataframe=dataframe,
                column_mapping={
                    "Order ID": "order_id",
                    "SKU ID": "sku_id",
                },
                lineage=lineage,
            )

        assert retry_result.rows_attempted == 2
        assert retry_result.rows_loaded == 2

        assert _count_raw_rows(
            postgres_connection,
            ingestion_file_id,
        ) == 2
    finally:
        _cleanup_test_records(
            postgres_connection,
            ingestion_file_id=ingestion_file_id,
            ingestion_run_id=ingestion_run_id,
        )


def test_failed_file_from_different_run_requires_reprocessing_policy(
    postgres_connection,
    tmp_path: Path,
) -> None:
    token = uuid4().hex

    source_file = tmp_path / f"orders_cross_run_retry_{token}.csv"
    source_file.write_text(
        (
            "Order ID,SKU ID\n"
            f"ORDER_CROSS_RUN_{token}_001,SKU_CROSS_RUN_{token}_001\n"
        ),
        encoding="utf-8",
    )

    metadata = build_file_metadata(
        source_name="orders",
        file_path=source_file,
    )

    first_run_id: int | None = None
    second_run_id: int | None = None
    ingestion_file_id: int | None = None

    try:
        first_run_id = _create_ingestion_run(
            postgres_connection
        )

        first_registration = register_file(
            connection=postgres_connection,
            ingestion_run_id=first_run_id,
            metadata=metadata,
        )
        postgres_connection.commit()

        ingestion_file_id = first_registration.ingestion_file_id

        _mark_file_status(
            postgres_connection,
            ingestion_file_id,
            "failed",
        )

        second_run_id = _create_ingestion_run(
            postgres_connection
        )

        second_registration = register_file(
            connection=postgres_connection,
            ingestion_run_id=second_run_id,
            metadata=metadata,
        )

        assert second_registration.is_duplicate is True
        assert second_registration.status == "failed"
        assert second_registration.ingestion_file_id == ingestion_file_id
        assert second_registration.ingestion_run_id == first_run_id

        decision = decide_file_processing(
            second_registration,
            current_ingestion_run_id=second_run_id,
        )

        assert decision.action == "block"
        assert decision.reason == (
            "cross_run_retry_requires_explicit_reprocessing_policy"
        )
        assert decision.should_process is False
    finally:
        if second_run_id is not None:
            _cleanup_test_records(
                postgres_connection,
                ingestion_file_id=None,
                ingestion_run_id=second_run_id,
            )

        _cleanup_test_records(
            postgres_connection,
            ingestion_file_id=ingestion_file_id,
            ingestion_run_id=first_run_id,
        )
