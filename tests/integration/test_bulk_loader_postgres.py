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
from ecommerce_pipeline.ingestion.load_contracts import get_load_contract


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


def test_orders_verified_load_contract_maps_all_business_columns(
    postgres_connection,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "orders_verified_contract_integration.csv"
    source_file.write_bytes(b"synthetic-orders-contract")

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
    contract = get_load_contract("orders")
    source_columns = tuple(contract.column_mapping)
    row = {
        source_column: f"value_{index:02d}"
        for index, source_column in enumerate(source_columns, start=1)
    }
    row["Order ID"] = "ORDER_CONTRACT_INT_001"
    row["SKU ID"] = "SKU_CONTRACT_INT_001"
    dataframe = pd.DataFrame([row], columns=source_columns)
    lineage = LineageMetadata(
        source_file=source_file.name,
        batch_id="batch_orders_contract_integration",
        file_hash=metadata.file_hash_sha256,
        pipeline_run_id=ingestion_run_id,
        ingestion_file_id=registered_file.ingestion_file_id,
        ingested_at=datetime(2026, 9, 8, tzinfo=UTC),
    )

    result = bulk_load_source(
        connection=postgres_connection,
        source_name="orders",
        dataframe=dataframe,
        column_mapping=contract.column_mapping,
        lineage=lineage,
    )

    assert result.rows_attempted == 1
    assert result.rows_loaded == 1
    target_columns = tuple(contract.column_mapping.values())
    query = f"""
        SELECT {", ".join(target_columns)},
               _source_row_number, _pipeline_run_id, _ingestion_file_id
        FROM raw.orders
        WHERE _ingestion_file_id = %s;
    """
    with postgres_connection.cursor() as cursor:
        cursor.execute(
            query,
            (registered_file.ingestion_file_id,),
        )
        loaded = cursor.fetchone()

    expected_business_values = tuple(
        row[column]
        for column in source_columns
    )
    assert loaded == (
        *expected_business_values,
        1,
        ingestion_run_id,
        registered_file.ingestion_file_id,
    )



def test_bulk_load_campaign_overview_into_postgres(
    postgres_connection,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "campaign_bulk_load_integration.xlsx"
    source_file.write_bytes(b"synthetic-campaign-integration")

    metadata = build_file_metadata(
        source_name="campaign_overview",
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

    current_shop_suffix = (
        " (\u0E23\u0E49\u0E32\u0E19\u0E04\u0E49\u0E32"
        "\u0E1B\u0E31\u0E08\u0E08\u0E38\u0E1A\u0E31\u0E19)"
    )

    dataframe = pd.DataFrame(
        {
            "\u0E15\u0E32\u0E21\u0E27\u0E31\u0E19": [
                "2026-08-01",
                "2026-08-02",
            ],
            "\u0E15\u0E49\u0E19\u0E17\u0E38\u0E19": [
                "100.00",
                "200.00",
            ],
            (
                "\u0E04\u0E33\u0E2A\u0E31\u0E48\u0E07"
                "\u0E0B\u0E37\u0E49\u0E2D SKU"
                + current_shop_suffix
            ): ["2", "4"],
            (
                "\u0E04\u0E48\u0E32\u0E43\u0E0A\u0E49"
                "\u0E08\u0E48\u0E32\u0E22\u0E15\u0E48\u0E2D"
                "\u0E04\u0E33\u0E2A\u0E31\u0E48\u0E07"
                "\u0E0B\u0E37\u0E49\u0E2D"
                + current_shop_suffix
            ): ["50.00", "50.00"],
            (
                "\u0E23\u0E32\u0E22\u0E44\u0E14\u0E49"
                "\u0E02\u0E31\u0E49\u0E19\u0E15\u0E49\u0E19"
                + current_shop_suffix
            ): ["300.00", "600.00"],
            ("ROI" + current_shop_suffix): ["3.00", "3.00"],
            "\u0E2A\u0E01\u0E38\u0E25\u0E40\u0E07\u0E34\u0E19": [
                "THB",
                "THB",
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
        batch_id="batch_campaign_integration_001",
        file_hash=metadata.file_hash_sha256,
        pipeline_run_id=ingestion_run_id,
        ingestion_file_id=registered_file.ingestion_file_id,
        ingested_at=ingested_at,
    )

    contract = get_load_contract("campaign_overview")

    result = bulk_load_source(
        connection=postgres_connection,
        source_name="campaign_overview",
        dataframe=dataframe,
        column_mapping=contract.column_mapping,
        lineage=lineage,
    )

    assert result.source_name == "campaign_overview"
    assert result.target_table == "raw.campaign_daily"
    assert result.rows_attempted == 2
    assert result.rows_loaded == 2

    query = """
        SELECT
            metric_date,
            ad_cost,
            sku_orders,
            cost_per_order,
            gross_revenue,
            roi,
            currency,
            _source_row_number,
            _pipeline_run_id,
            _ingestion_file_id
        FROM raw.campaign_daily
        WHERE _ingestion_file_id = %s
        ORDER BY _source_row_number;
    """

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            query,
            (registered_file.ingestion_file_id,),
        )
        rows = cursor.fetchall()

    assert rows == [
        (
            "2026-08-01",
            "100.00",
            "2",
            "50.00",
            "300.00",
            "3.00",
            "THB",
            1,
            ingestion_run_id,
            registered_file.ingestion_file_id,
        ),
        (
            "2026-08-02",
            "200.00",
            "4",
            "50.00",
            "600.00",
            "3.00",
            "THB",
            2,
            ingestion_run_id,
            registered_file.ingestion_file_id,
        ),
    ]


def test_bulk_load_shop_analytics_into_postgres(
    postgres_connection,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "shop_analytics_bulk_load_integration.xlsx"
    source_file.write_bytes(b"synthetic-shop-analytics-integration")

    metadata = build_file_metadata(
        source_name="shop_analytics",
        file_path=source_file,
    )
    ingestion_run_id = create_test_ingestion_run(postgres_connection)
    registered_file = register_file(
        connection=postgres_connection,
        ingestion_run_id=ingestion_run_id,
        metadata=metadata,
    )

    contract = get_load_contract("shop_analytics")
    dataframe = pd.DataFrame(
        {
            source_column: [f"value_{index:02d}"]
            for index, source_column in enumerate(
                contract.column_mapping,
                start=1,
            )
        }
    )

    lineage = LineageMetadata(
        source_file=source_file.name,
        batch_id="batch_shop_analytics_integration_001",
        file_hash=metadata.file_hash_sha256,
        pipeline_run_id=ingestion_run_id,
        ingestion_file_id=registered_file.ingestion_file_id,
        ingested_at=datetime(2026, 8, 17, tzinfo=UTC),
    )

    result = bulk_load_source(
        connection=postgres_connection,
        source_name="shop_analytics",
        dataframe=dataframe,
        column_mapping=contract.column_mapping,
        lineage=lineage,
    )

    assert result.source_name == "shop_analytics"
    assert result.target_table == "raw.shop_daily"
    assert result.rows_attempted == 1
    assert result.rows_loaded == 1

    target_columns = tuple(contract.column_mapping.values())
    query = f"""
        SELECT
            {", ".join(target_columns)},
            _source_row_number,
            _pipeline_run_id,
            _ingestion_file_id
        FROM raw.shop_daily
        WHERE _ingestion_file_id = %s;
    """

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            query,
            (registered_file.ingestion_file_id,),
        )
        row = cursor.fetchone()

    expected_business_values = tuple(
        f"value_{index:02d}"
        for index in range(1, 29)
    )

    assert row == (
        *expected_business_values,
        1,
        ingestion_run_id,
        registered_file.ingestion_file_id,
    )
