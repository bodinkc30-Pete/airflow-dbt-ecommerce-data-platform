from datetime import UTC, datetime

import pandas as pd
import pytest

from ecommerce_pipeline.ingestion.bulk_loader import (
    LineageMetadata,
    _split_target_table,
    prepare_influencer_roster_dataframe,
    prepare_product_master_dataframe,
    prepare_raw_dataframe,
)


def _lineage() -> LineageMetadata:
    return LineageMetadata(
        source_file="orders.csv",
        batch_id="batch_001",
        file_hash="a" * 64,
        pipeline_run_id=10,
        ingestion_file_id=20,
        ingested_at=datetime(2026, 8, 17, 0, 0, tzinfo=UTC),
    )


def test_split_target_table_returns_schema_and_table() -> None:
    assert _split_target_table("raw.orders") == ("raw", "orders")


@pytest.mark.parametrize(
    "target_table",
    [
        "orders",
        ".orders",
        "raw.",
    ],
)
def test_split_target_table_rejects_invalid_format(
    target_table: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="schema.table format",
    ):
        _split_target_table(target_table)


def test_prepare_raw_dataframe_maps_columns_and_adds_lineage() -> None:
    dataframe = pd.DataFrame(
        {
            "Order ID": ["ORDER_001", "ORDER_002"],
            "SKU ID": ["SKU_001", "SKU_002"],
        }
    )

    prepared = prepare_raw_dataframe(
        dataframe=dataframe,
        column_mapping={
            "Order ID": "order_id",
            "SKU ID": "sku_id",
        },
        lineage=_lineage(),
    )

    assert list(prepared.columns) == [
        "order_id",
        "sku_id",
        "_source_file",
        "_source_row_number",
        "_batch_id",
        "_file_hash",
        "_ingested_at",
        "_pipeline_run_id",
        "_ingestion_file_id",
    ]

    assert prepared["order_id"].tolist() == [
        "ORDER_001",
        "ORDER_002",
    ]
    assert prepared["sku_id"].tolist() == [
        "SKU_001",
        "SKU_002",
    ]
    assert prepared["_source_row_number"].tolist() == [1, 2]
    assert prepared["_source_file"].tolist() == [
        "orders.csv",
        "orders.csv",
    ]
    assert prepared["_batch_id"].tolist() == [
        "batch_001",
        "batch_001",
    ]
    assert prepared["_file_hash"].tolist() == [
        "a" * 64,
        "a" * 64,
    ]
    assert prepared["_pipeline_run_id"].tolist() == [10, 10]
    assert prepared["_ingestion_file_id"].tolist() == [20, 20]


def test_prepare_raw_dataframe_respects_source_row_start() -> None:
    dataframe = pd.DataFrame(
        {
            "Order ID": ["ORDER_001", "ORDER_002"],
        }
    )

    prepared = prepare_raw_dataframe(
        dataframe=dataframe,
        column_mapping={
            "Order ID": "order_id",
        },
        lineage=_lineage(),
        source_row_start=100,
    )

    assert prepared["_source_row_number"].tolist() == [100, 101]


def test_prepare_raw_dataframe_normalizes_nan_to_none() -> None:
    dataframe = pd.DataFrame(
        {
            "Order ID": ["ORDER_001", None],
            "SKU ID": ["SKU_001", float("nan")],
        }
    )

    prepared = prepare_raw_dataframe(
        dataframe=dataframe,
        column_mapping={
            "Order ID": "order_id",
            "SKU ID": "sku_id",
        },
        lineage=_lineage(),
    )

    assert prepared.loc[1, "order_id"] is None
    assert prepared.loc[1, "sku_id"] is None


def test_prepare_raw_dataframe_rejects_missing_mapped_column() -> None:
    dataframe = pd.DataFrame(
        {
            "Order ID": ["ORDER_001"],
        }
    )

    with pytest.raises(
        ValueError,
        match="missing mapped columns",
    ):
        prepare_raw_dataframe(
            dataframe=dataframe,
            column_mapping={
                "Order ID": "order_id",
                "SKU ID": "sku_id",
            },
            lineage=_lineage(),
        )


def test_prepare_raw_dataframe_rejects_duplicate_destination_columns() -> None:
    dataframe = pd.DataFrame(
        {
            "Order ID": ["ORDER_001"],
            "SKU ID": ["SKU_001"],
        }
    )

    with pytest.raises(
        ValueError,
        match="duplicate destination columns",
    ):
        prepare_raw_dataframe(
            dataframe=dataframe,
            column_mapping={
                "Order ID": "identifier",
                "SKU ID": "identifier",
            },
            lineage=_lineage(),
        )


def test_prepare_raw_dataframe_rejects_non_positive_source_row_start() -> None:
    dataframe = pd.DataFrame(
        {
            "Order ID": ["ORDER_001"],
        }
    )

    with pytest.raises(
        ValueError,
        match="source_row_start must be positive",
    ):
        prepare_raw_dataframe(
            dataframe=dataframe,
            column_mapping={
                "Order ID": "order_id",
            },
            lineage=_lineage(),
            source_row_start=0,
        )


@pytest.mark.parametrize(
    ("field_name", "replacement", "message"),
    [
        ("source_file", "", "source_file must not be blank"),
        ("batch_id", "   ", "batch_id must not be blank"),
        (
            "file_hash",
            "a" * 63,
            "file_hash must contain exactly 64 characters",
        ),
        (
            "file_hash",
            "g" * 64,
            "file_hash must contain only hexadecimal characters",
        ),
        (
            "pipeline_run_id",
            0,
            "pipeline_run_id must be positive",
        ),
        (
            "ingestion_file_id",
            0,
            "ingestion_file_id must be positive",
        ),
    ],
)
def test_prepare_raw_dataframe_rejects_invalid_lineage(
    field_name: str,
    replacement: object,
    message: str,
) -> None:
    lineage_values = {
        "source_file": "orders.csv",
        "batch_id": "batch_001",
        "file_hash": "a" * 64,
        "pipeline_run_id": 10,
        "ingestion_file_id": 20,
        "ingested_at": datetime(
            2026,
            8,
            17,
            0,
            0,
            tzinfo=UTC,
        ),
    }
    lineage_values[field_name] = replacement

    lineage = LineageMetadata(**lineage_values)

    dataframe = pd.DataFrame(
        {
            "Order ID": ["ORDER_001"],
        }
    )

    with pytest.raises(
        ValueError,
        match=message,
    ):
        prepare_raw_dataframe(
            dataframe=dataframe,
            column_mapping={
                "Order ID": "order_id",
            },
            lineage=lineage,
        )


def test_prepare_raw_dataframe_handles_empty_dataframe() -> None:
    dataframe = pd.DataFrame(
        columns=[
            "Order ID",
            "SKU ID",
        ]
    )

    prepared = prepare_raw_dataframe(
        dataframe=dataframe,
        column_mapping={
            "Order ID": "order_id",
            "SKU ID": "sku_id",
        },
        lineage=_lineage(),
    )

    assert prepared.empty
    assert list(prepared.columns) == [
        "order_id",
        "sku_id",
        "_source_file",
        "_source_row_number",
        "_batch_id",
        "_file_hash",
        "_ingested_at",
        "_pipeline_run_id",
        "_ingestion_file_id",
    ]


def test_prepare_raw_dataframe_does_not_mutate_input_dataframe() -> None:
    dataframe = pd.DataFrame(
        {
            "Order ID": ["ORDER_001"],
            "SKU ID": ["SKU_001"],
        }
    )
    original = dataframe.copy(deep=True)

    prepare_raw_dataframe(
        dataframe=dataframe,
        column_mapping={
            "Order ID": "order_id",
            "SKU ID": "sku_id",
        },
        lineage=_lineage(),
    )

    pd.testing.assert_frame_equal(
        dataframe,
        original,
    )



def test_prepare_product_master_dataframe_preserves_full_payload() -> None:
    product_status_header = (
        "\u0E2A\u0E16\u0E32\u0E19\u0E30\u0E23\u0E32\u0E22"
        "\u0E01\u0E32\u0E23\u0E2A\u0E34\u0E19\u0E04\u0E49\u0E32"
    )
    dataframe = pd.DataFrame(
        {
            "\u0E0A\u0E37\u0E48\u0E2D": ["Synthetic product"],
            "\u0E23\u0E2B\u0E31\u0E2A\u0E2A\u0E34\u0E19\u0E04\u0E49\u0E32": ["PROD_SYN_001"],
            "\u0E0A\u0E48\u0E27\u0E07 GMV": ["A"],
            product_status_header: ["active"],
            "all::GMV": [123.4],
            "all::Orders": [None],
        }
    )
    mapping = {
        "\u0E0A\u0E37\u0E48\u0E2D": "product_name",
        "\u0E23\u0E2B\u0E31\u0E2A\u0E2A\u0E34\u0E19\u0E04\u0E49\u0E32": "product_id",
        "\u0E0A\u0E48\u0E27\u0E07 GMV": "gmv_tier",
        product_status_header: "product_status",
    }

    prepared = prepare_product_master_dataframe(
        dataframe=dataframe,
        column_mapping=mapping,
        lineage=_lineage(),
    )

    assert list(prepared.columns) == [
        "product_id",
        "product_name",
        "gmv_tier",
        "product_status",
        "source_payload",
        "_source_file",
        "_source_row_number",
        "_batch_id",
        "_file_hash",
        "_ingested_at",
        "_pipeline_run_id",
        "_ingestion_file_id",
    ]
    payload = prepared.loc[0, "source_payload"].adapted
    assert payload["all::GMV"] == "123.4"
    assert payload["all::Orders"] is None
    assert len(payload) == 6
    assert prepared.loc[0, "product_id"] == "PROD_SYN_001"
    assert prepared.loc[0, "product_name"] == "Synthetic product"


def test_prepare_influencer_roster_dataframe_preserves_full_payload() -> None:
    dataframe = pd.DataFrame(
        {
            "Influencer": ["Synthetic Creator"],
            "Follower": ["10000"],
            "Engangement Rate%": ["0.05"],
            "BUDGET": ["2000"],
            "audience_gender": ["synthetic"],
        }
    )
    mapping = {
        "Influencer": "influencer_name",
        "Follower": "follower_count",
        "Engangement Rate%": "engagement_rate",
        "BUDGET": "budget",
    }
    prepared = prepare_influencer_roster_dataframe(
        dataframe=dataframe, column_mapping=mapping, lineage=_lineage()
    )
    assert prepared.loc[0, "influencer_name"] == "Synthetic Creator"
    assert prepared.loc[0, "source_payload"].adapted["audience_gender"] == "synthetic"
    assert len(prepared.loc[0, "source_payload"].adapted) == 5
