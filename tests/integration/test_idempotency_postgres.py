import os
from pathlib import Path

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
            'pytest_idempotency',
            'test',
            'running'
        )
        RETURNING ingestion_run_id;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    return row[0]


def _mark_file_success(
    connection,
    ingestion_file_id: int,
    rows_loaded: int,
) -> None:
    query = """
        UPDATE audit.ingestion_files
        SET
            status = 'success',
            processing_started_at = CURRENT_TIMESTAMP,
            processing_finished_at = CURRENT_TIMESTAMP,
            rows_loaded = %s
        WHERE ingestion_file_id = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                rows_loaded,
                ingestion_file_id,
            ),
        )


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


def test_duplicate_successful_file_is_skipped_without_duplicate_raw_rows(
    postgres_connection,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "orders_idempotency.csv"
    source_file.write_text(
        (
            "Order ID,SKU ID\n"
            "ORDER_IDEMPOTENT_001,SKU_IDEMPOTENT_001\n"
            "ORDER_IDEMPOTENT_002,SKU_IDEMPOTENT_002\n"
        ),
        encoding="utf-8",
    )

    metadata = build_file_metadata(
        source_name="orders",
        file_path=source_file,
    )

    ingestion_run_id = _create_ingestion_run(
        postgres_connection
    )

    first_registration = register_file(
        connection=postgres_connection,
        ingestion_run_id=ingestion_run_id,
        metadata=metadata,
    )

    first_decision = decide_file_processing(
        first_registration,
        current_ingestion_run_id=ingestion_run_id,
    )

    assert first_decision.should_process is True
    assert first_decision.action == "process"

    dataframe = pd.DataFrame(
        {
            "Order ID": [
                "ORDER_IDEMPOTENT_001",
                "ORDER_IDEMPOTENT_002",
            ],
            "SKU ID": [
                "SKU_IDEMPOTENT_001",
                "SKU_IDEMPOTENT_002",
            ],
        }
    )

    lineage = LineageMetadata(
        source_file=source_file.name,
        batch_id="batch_idempotency_001",
        file_hash=metadata.file_hash_sha256,
        pipeline_run_id=ingestion_run_id,
        ingestion_file_id=first_registration.ingestion_file_id,
    )

    first_load = bulk_load_source(
        connection=postgres_connection,
        source_name="orders",
        dataframe=dataframe,
        column_mapping={
            "Order ID": "order_id",
            "SKU ID": "sku_id",
        },
        lineage=lineage,
    )

    assert first_load.rows_loaded == 2

    _mark_file_success(
        postgres_connection,
        ingestion_file_id=first_registration.ingestion_file_id,
        rows_loaded=first_load.rows_loaded,
    )

    rows_after_first_load = _count_raw_rows(
        postgres_connection,
        first_registration.ingestion_file_id,
    )

    assert rows_after_first_load == 2

    second_registration = register_file(
        connection=postgres_connection,
        ingestion_run_id=ingestion_run_id,
        metadata=metadata,
    )

    assert second_registration.is_duplicate is True
    assert (
        second_registration.ingestion_file_id
        == first_registration.ingestion_file_id
    )
    assert second_registration.status == "success"

    second_decision = decide_file_processing(
        second_registration,
        current_ingestion_run_id=ingestion_run_id,
    )

    assert second_decision.should_process is False
    assert second_decision.action == "skip_duplicate"
    assert second_decision.reason == "already_processed"

    rows_after_duplicate_rerun = _count_raw_rows(
        postgres_connection,
        first_registration.ingestion_file_id,
    )

    assert rows_after_duplicate_rerun == 2
