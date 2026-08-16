import os
from datetime import UTC, datetime
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


def create_test_ingestion_run(connection) -> int:
    query = """
        INSERT INTO audit.ingestion_runs (
            pipeline_name,
            run_type,
            status
        )
        VALUES (
            'pytest_bulk_loader',
            'manual',
            'running'
        )
        RETURNING ingestion_run_id;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    return row[0]


def test_bulk_load_orders_into_postgres(
    postgres_connection,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "orders_bulk_load_integration.csv"
    source_file.write_text(
        (
            "Order ID,SKU ID\n"
            "ORDER_BULK_INT_001,SKU_BULK_INT_001\n"
            "ORDER_BULK_INT_002,SKU_BULK_INT_002\n"
        ),
        encoding="utf-8",
    )

    metadata = build_file_metadata(
        source_name="orders",
        file_path=source_file,
    )

    ingestion_run_id = create_test_ingestion_run(
        postgres_connection
    )

    registered_file = register_file(
        connection=postgres_connection,
        ingestion_run_id=ingestion_run_id,
        metadata=metadata,
    )

    dataframe = pd.DataFrame(
        {
            "Order ID": [
                "ORDER_BULK_INT_001",
                "ORDER_BULK_INT_002",
            ],
            "SKU ID": [
                "SKU_BULK_INT_001",
                "SKU_BULK_INT_002",
            ],
        }
    )

    ingested_at = datetime(
        2026,
        8,
        17,
        0,
        0,
        tzinfo=UTC,
    )

    lineage = LineageMetadata(
        source_file=source_file.name,
        batch_id="batch_bulk_integration_001",
        file_hash=metadata.file_hash_sha256,
        pipeline_run_id=ingestion_run_id,
        ingestion_file_id=registered_file.ingestion_file_id,
        ingested_at=ingested_at,
    )

    result = bulk_load_source(
        connection=postgres_connection,
        source_name="orders",
        dataframe=dataframe,
        column_mapping={
            "Order ID": "order_id",
            "SKU ID": "sku_id",
        },
        lineage=lineage,
    )

    assert result.source_name == "orders"
    assert result.target_table == "raw.orders"
    assert result.rows_attempted == 2
    assert result.rows_loaded == 2

    query = """
        SELECT
            order_id,
            sku_id,
            _source_file,
            _source_row_number,
            _batch_id,
            _file_hash,
            _ingested_at,
            _pipeline_run_id,
            _ingestion_file_id
        FROM raw.orders
        WHERE _ingestion_file_id = %s
        ORDER BY _source_row_number;
    """

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            query,
            (registered_file.ingestion_file_id,),
        )
        rows = cursor.fetchall()

    assert len(rows) == 2

    assert rows[0] == (
        "ORDER_BULK_INT_001",
        "SKU_BULK_INT_001",
        source_file.name,
        1,
        "batch_bulk_integration_001",
        metadata.file_hash_sha256,
        ingested_at,
        ingestion_run_id,
        registered_file.ingestion_file_id,
    )

    assert rows[1] == (
        "ORDER_BULK_INT_002",
        "SKU_BULK_INT_002",
        source_file.name,
        2,
        "batch_bulk_integration_001",
        metadata.file_hash_sha256,
        ingested_at,
        ingestion_run_id,
        registered_file.ingestion_file_id,
    )
