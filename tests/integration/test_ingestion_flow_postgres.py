import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from ecommerce_pipeline.ingestion.audit_lifecycle import (
    mark_file_processing,
    mark_file_success,
)
from ecommerce_pipeline.ingestion.bulk_loader import (
    LineageMetadata,
    bulk_load_source,
)
from ecommerce_pipeline.ingestion.extraction_adapters import (
    extract_source_file,
)
from ecommerce_pipeline.ingestion.file_registry import (
    build_file_metadata,
    connect_postgres,
    register_file,
)
from ecommerce_pipeline.ingestion.schema_validation import (
    validate_schema,
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
            'pytest_ingestion_flow',
            'test',
            'running'
        )
        RETURNING ingestion_run_id;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Failed to create ingestion run")

    return int(row[0])


def _cleanup_ingestion_run(
    connection,
    *,
    ingestion_run_id: int,
) -> None:
    connection.rollback()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM raw.orders
            WHERE _pipeline_run_id = %s;
            """,
            (ingestion_run_id,),
        )

        cursor.execute(
            """
            DELETE FROM audit.ingestion_files
            WHERE ingestion_run_id = %s;
            """,
            (ingestion_run_id,),
        )

        cursor.execute(
            """
            DELETE FROM audit.ingestion_runs
            WHERE ingestion_run_id = %s;
            """,
            (ingestion_run_id,),
        )

    connection.commit()


def test_orders_cross_component_ingestion_flow(
    postgres_connection,
    tmp_path: Path,
) -> None:
    unique_token = uuid4().hex[:12]

    source_file = tmp_path / f"orders_ingestion_flow_{unique_token}.csv"

    columns = ["Order ID", "SKU ID"] + [
        f"column_{index}"
        for index in range(3, 66)
    ]

    rows = [
        [
            f"ORDER_FLOW_{unique_token}_001",
            f"SKU_FLOW_{unique_token}_001",
        ]
        + [str(index) for index in range(3, 66)],
        [
            f"ORDER_FLOW_{unique_token}_002",
            f"SKU_FLOW_{unique_token}_002",
        ]
        + [str(index) for index in range(3, 66)],
    ]

    pd.DataFrame(rows, columns=columns).to_csv(
        source_file,
        index=False,
    )

    ingestion_run_id: int | None = None

    try:
        extraction = extract_source_file(
            source_name="orders",
            file_path=source_file,
        )

        assert extraction.source_name == "orders"
        assert extraction.row_count == 2
        assert extraction.column_count == 65

        validation = validate_schema(
            source_name="orders",
            observed_columns=extraction.columns,
        )

        assert validation.status == "VALID"
        assert validation.observed_column_count == 65
        assert validation.expected_column_count == 65
        assert validation.missing_required_columns == ()
        assert validation.duplicate_columns == ()
        assert validation.issues == ()

        metadata = build_file_metadata(
            source_name="orders",
            file_path=source_file,
        )

        with transaction_scope(postgres_connection):
            ingestion_run_id = _create_ingestion_run(
                postgres_connection
            )

            registered_file = register_file(
                connection=postgres_connection,
                ingestion_run_id=ingestion_run_id,
                metadata=metadata,
            )

        assert registered_file.is_duplicate is False
        assert registered_file.status == "discovered"

        with transaction_scope(postgres_connection):
            processing_state = mark_file_processing(
                connection=postgres_connection,
                ingestion_file_id=registered_file.ingestion_file_id,
                rows_discovered=extraction.row_count,
            )

        assert processing_state.status == "processing"
        assert processing_state.rows_discovered == 2

        ingested_at = datetime(
            2026,
            8,
            19,
            0,
            0,
            tzinfo=UTC,
        )

        lineage = LineageMetadata(
            source_file=source_file.name,
            batch_id=f"batch_ingestion_flow_{unique_token}",
            file_hash=metadata.file_hash_sha256,
            pipeline_run_id=ingestion_run_id,
            ingestion_file_id=registered_file.ingestion_file_id,
            ingested_at=ingested_at,
        )

        with transaction_scope(postgres_connection):
            load_result = bulk_load_source(
                connection=postgres_connection,
                source_name="orders",
                dataframe=extraction.dataframe,
                column_mapping={
                    "Order ID": "order_id",
                    "SKU ID": "sku_id",
                },
                lineage=lineage,
            )

            success_state = mark_file_success(
                connection=postgres_connection,
                ingestion_file_id=registered_file.ingestion_file_id,
                rows_discovered=extraction.row_count,
                rows_loaded=load_result.rows_loaded,
                rows_rejected=(
                    extraction.row_count
                    - load_result.rows_loaded
                ),
            )

        assert load_result.source_name == "orders"
        assert load_result.target_table == "raw.orders"
        assert load_result.rows_attempted == 2
        assert load_result.rows_loaded == 2

        assert success_state.status == "success"
        assert success_state.rows_discovered == 2
        assert success_state.rows_loaded == 2
        assert success_state.rows_rejected == 0
        assert success_state.error_message is None

        with postgres_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    order_id,
                    sku_id,
                    _source_file,
                    _file_hash,
                    _pipeline_run_id,
                    _ingestion_file_id
                FROM raw.orders
                WHERE _ingestion_file_id = %s
                ORDER BY _source_row_number;
                """,
                (registered_file.ingestion_file_id,),
            )
            raw_rows = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    status,
                    processing_started_at,
                    processing_finished_at,
                    rows_discovered,
                    rows_loaded,
                    rows_rejected,
                    error_message
                FROM audit.ingestion_files
                WHERE ingestion_file_id = %s;
                """,
                (registered_file.ingestion_file_id,),
            )
            audit_row = cursor.fetchone()

        assert len(raw_rows) == 2

        assert raw_rows[0] == (
            f"ORDER_FLOW_{unique_token}_001",
            f"SKU_FLOW_{unique_token}_001",
            source_file.name,
            metadata.file_hash_sha256,
            ingestion_run_id,
            registered_file.ingestion_file_id,
        )

        assert raw_rows[1] == (
            f"ORDER_FLOW_{unique_token}_002",
            f"SKU_FLOW_{unique_token}_002",
            source_file.name,
            metadata.file_hash_sha256,
            ingestion_run_id,
            registered_file.ingestion_file_id,
        )

        assert audit_row is not None
        assert audit_row[0] == "success"
        assert audit_row[1] is not None
        assert audit_row[2] is not None
        assert audit_row[3] == 2
        assert audit_row[4] == 2
        assert audit_row[5] == 0
        assert audit_row[6] is None

    finally:
        if ingestion_run_id is not None:
            _cleanup_ingestion_run(
                postgres_connection,
                ingestion_run_id=ingestion_run_id,
            )
