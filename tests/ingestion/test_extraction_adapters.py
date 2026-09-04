from pathlib import Path

import pandas as pd
import pytest

from ecommerce_pipeline.ingestion.extraction_adapters import (
    canonicalize_product_master_headers,
    extract_source_file,
)


def test_canonicalize_product_master_headers_builds_group_metric_keys() -> None:
    group_headers = [
        "Product",
        None,
        "ทั้งหมด",
        None,
    ]
    metric_headers = [
        "Product ID",
        "Product name",
        "GMV",
        "CTR",
    ]

    result = canonicalize_product_master_headers(
        group_headers=group_headers,
        metric_headers=metric_headers,
    )

    assert result == (
        "Product::Product ID",
        "Product::Product name",
        "ทั้งหมด::GMV",
        "ทั้งหมด::CTR",
    )


def test_canonicalize_product_master_headers_deduplicates_names() -> None:
    result = canonicalize_product_master_headers(
        group_headers=["ทั้งหมด", None, None],
        metric_headers=["GMV", "GMV", "GMV"],
    )

    assert result == (
        "ทั้งหมด::GMV",
        "ทั้งหมด::GMV__1",
        "ทั้งหมด::GMV__2",
    )


def test_canonicalize_product_master_headers_rejects_length_mismatch() -> None:
    with pytest.raises(
        ValueError,
        match="header lengths do not match",
    ):
        canonicalize_product_master_headers(
            group_headers=["A"],
            metric_headers=["A", "B"],
        )


def test_extract_orders_csv_uses_registered_header_row(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "orders.csv"

    columns = ["Order ID", "SKU ID"] + [
        f"column_{index}"
        for index in range(3, 66)
    ]
    row = ["ORDER_001", "SKU_001"] + [
        str(index)
        for index in range(3, 66)
    ]

    pd.DataFrame(
        [row],
        columns=columns,
    ).to_csv(
        file_path,
        index=False,
    )

    result = extract_source_file(
        source_name="orders",
        file_path=file_path,
    )

    assert result.source_name == "orders"
    assert result.engine == "pandas_csv"
    assert result.row_count == 1
    assert result.column_count == 65
    assert result.columns[0] == "Order ID"
    assert result.columns[1] == "SKU ID"
    assert result.dataframe.iloc[0]["Order ID"] == "ORDER_001"
    assert result.dataframe.iloc[0]["SKU ID"] == "SKU_001"


def test_extract_shop_analytics_excel_uses_header_row_8(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "shop.xlsx"

    rows: list[list[object]] = []

    for _ in range(8):
        rows.append(["metadata"] + [""] * 27)

    columns = ["Date"] + [
        f"metric_{index}"
        for index in range(2, 29)
    ]
    rows.append(columns)

    data_row = ["2026-08-13"] + [
        str(index)
        for index in range(2, 29)
    ]
    rows.append(data_row)

    pd.DataFrame(rows).to_excel(
        file_path,
        index=False,
        header=False,
        sheet_name="Sheet1",
    )

    result = extract_source_file(
        source_name="shop_analytics",
        file_path=file_path,
    )

    assert result.engine == "pandas_excel"
    assert result.row_count == 1
    assert result.column_count == 28
    assert result.columns[0] == "Date"
    assert result.dataframe.iloc[0]["Date"] == "2026-08-13"


def test_extract_live_performance_excel_uses_header_row_2(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "live.xlsx"

    rows = [
        ["metadata"] + [""] * 17,
        ["metadata"] + [""] * 17,
    ]

    columns = ["Date"] + [
        f"metric_{index}"
        for index in range(2, 19)
    ]
    rows.append(columns)

    rows.append(
        ["2026-08-13"]
        + [
            str(index)
            for index in range(2, 19)
        ]
    )

    pd.DataFrame(rows).to_excel(
        file_path,
        index=False,
        header=False,
        sheet_name="Sheet1",
    )

    result = extract_source_file(
        source_name="live_performance",
        file_path=file_path,
    )

    assert result.engine == "pandas_excel"
    assert result.row_count == 1
    assert result.column_count == 18
    assert result.columns[0] == "Date"


def test_extract_product_master_uses_two_level_headers(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "product_master.xlsx"

    column_count = 176

    row_0 = ["metadata"] + [""] * (column_count - 1)
    row_1 = ["metadata"] + [""] * (column_count - 1)

    group_headers: list[object] = [
        "Product",
        None,
        "ทั้งหมด",
    ] + [
        "Group"
        for _ in range(column_count - 3)
    ]

    metric_headers: list[object] = [
        "Product ID",
        "Product name",
        "GMV",
    ] + [
        f"metric_{index}"
        for index in range(4, column_count + 1)
    ]

    data_row = [
        "1730000000000000001",
        "Sample Product",
        "1234.56",
    ] + [
        str(index)
        for index in range(4, column_count + 1)
    ]

    pd.DataFrame(
        [
            row_0,
            row_1,
            group_headers,
            metric_headers,
            data_row,
        ]
    ).to_excel(
        file_path,
        index=False,
        header=False,
        sheet_name="Sheet1",
    )

    result = extract_source_file(
        source_name="product_master",
        file_path=file_path,
    )

    assert result.engine == "product_master_two_level"
    assert result.row_count == 1
    assert result.column_count == 176
    assert result.columns[0] == "Product::Product ID"
    assert result.columns[1] == "Product::Product name"
    assert result.columns[2] == "ทั้งหมด::GMV"
    assert result.dataframe.iloc[0, 0] == "1730000000000000001"


def test_extract_source_file_rejects_missing_file(
    tmp_path: Path,
) -> None:
    missing_file = tmp_path / "missing.csv"

    with pytest.raises(
        FileNotFoundError,
        match="Source file does not exist",
    ):
        extract_source_file(
            source_name="orders",
            file_path=missing_file,
        )


def test_extract_source_file_rejects_directory(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "not-a-file"
    directory.mkdir()

    with pytest.raises(
        ValueError,
        match="Source path is not a file",
    ):
        extract_source_file(
            source_name="orders",
            file_path=directory,
        )


def test_extract_source_file_rejects_empty_file(
    tmp_path: Path,
) -> None:
    empty_file = tmp_path / "empty.csv"
    empty_file.touch()

    with pytest.raises(
        ValueError,
        match="Source file is empty",
    ):
        extract_source_file(
            source_name="orders",
            file_path=empty_file,
        )


def test_extract_source_file_rejects_unknown_source(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "sample.csv"
    file_path.write_text(
        "a,b\n1,2\n",
        encoding="utf-8",
    )

    with pytest.raises(
        KeyError,
        match="Unknown source",
    ):
        extract_source_file(
            source_name="does_not_exist",
            file_path=file_path,
        )


def test_extraction_result_preserves_resolved_file_path(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "orders.csv"

    columns = ["Order ID", "SKU ID"] + [
        f"column_{index}"
        for index in range(3, 66)
    ]

    pd.DataFrame(
        [["ORDER_001", "SKU_001"] + [""] * 63],
        columns=columns,
    ).to_csv(
        file_path,
        index=False,
    )

    result = extract_source_file(
        source_name="orders",
        file_path=str(file_path),
    )

    assert result.file_path == file_path.resolve()


def test_extract_campaign_overview_excludes_non_daily_footer_row(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "campaign.xlsx"

    date_header = "\u0e15\u0e32\u0e21\u0e27\u0e31\u0e19"

    pd.DataFrame(
        [
            ["2026-07-01", "10", "1", "10", "20", "2", "THB"],
            ["2026-07-02", "20", "2", "10", "40", "2", "THB"],
            ["-", "30", "3", "10", "60", "2", "THB"],
        ],
        columns=[
            date_header,
            "metric_2",
            "metric_3",
            "metric_4",
            "metric_5",
            "metric_6",
            "metric_7",
        ],
    ).to_excel(
        file_path,
        index=False,
        sheet_name="Sheet1",
    )

    result = extract_source_file(
        source_name="campaign_overview",
        file_path=file_path,
    )

    assert result.row_count == 2
    assert result.dataframe.iloc[:, 0].tolist() == [
        "2026-07-01",
        "2026-07-02",
    ]
