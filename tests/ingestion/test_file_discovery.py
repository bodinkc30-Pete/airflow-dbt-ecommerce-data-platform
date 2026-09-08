from pathlib import Path

import pytest

from ecommerce_pipeline.ingestion.file_discovery import (
    discover_all_sources,
    discover_source_files,
)


def test_discover_source_files_finds_matching_file(
    tmp_path: Path,
) -> None:
    matching_file = tmp_path / "ทั้งหมด คำสั่งซื้อ-2026-08-13-12_26.csv"
    matching_file.write_text(
        "order_id,sku_id\nORDER_001,SKU_001\n",
        encoding="utf-8",
    )

    discovered = discover_source_files(
        source_name="orders",
        input_directory=tmp_path,
    )

    assert len(discovered) == 1
    assert discovered[0].source_name == "orders"
    assert discovered[0].file_name == matching_file.name
    assert discovered[0].file_path == matching_file.resolve()


def test_discover_source_files_ignores_non_matching_files(
    tmp_path: Path,
) -> None:
    matching_file = tmp_path / "ทั้งหมด คำสั่งซื้อ-2026-08-13-12_26.csv"
    ignored_file = tmp_path / "random.csv"

    matching_file.write_text("orders", encoding="utf-8")
    ignored_file.write_text("ignore", encoding="utf-8")

    discovered = discover_source_files(
        source_name="orders",
        input_directory=tmp_path,
    )

    assert len(discovered) == 1
    assert discovered[0].file_name == matching_file.name


def test_discover_source_files_returns_empty_when_no_match(
    tmp_path: Path,
) -> None:
    discovered = discover_source_files(
        source_name="orders",
        input_directory=tmp_path,
    )

    assert discovered == ()


def test_discover_source_files_rejects_missing_directory(
    tmp_path: Path,
) -> None:
    missing_directory = tmp_path / "missing"

    with pytest.raises(
        FileNotFoundError,
        match="Input directory does not exist",
    ):
        discover_source_files(
            source_name="orders",
            input_directory=missing_directory,
        )


def test_discover_source_files_rejects_file_as_directory(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "not_a_directory.txt"
    file_path.write_text("sample", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="Input path is not a directory",
    ):
        discover_source_files(
            source_name="orders",
            input_directory=file_path,
        )


def test_discover_source_files_rejects_unknown_source(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        KeyError,
        match="Unknown source 'unknown_source'",
    ):
        discover_source_files(
            source_name="unknown_source",
            input_directory=tmp_path,
        )


def test_multiple_file_source_returns_all_matches_in_sorted_order(
    tmp_path: Path,
) -> None:
    later_file = tmp_path / "Product Card Traffic Stats_20260813054100.xlsx"
    earlier_file = tmp_path / "Product Card Traffic Stats_20260813054044.xlsx"

    later_file.write_bytes(b"later")
    earlier_file.write_bytes(b"earlier")

    discovered = discover_source_files(
        source_name="product_card_traffic",
        input_directory=tmp_path,
    )

    assert len(discovered) == 2
    assert [item.file_name for item in discovered] == [
        earlier_file.name,
        later_file.name,
    ]


def test_shop_analytics_returns_multiple_matching_files(
    tmp_path: Path,
) -> None:
    first_file = tmp_path / "Shop-Analytics_Key-metrics_20260714-1.xlsx"
    second_file = tmp_path / "Shop-Analytics_Key-metrics_20260714.xlsx"

    first_file.write_bytes(b"first")
    second_file.write_bytes(b"second")

    discovered = discover_source_files(
        source_name="shop_analytics",
        input_directory=tmp_path,
    )

    assert len(discovered) == 2
    assert [item.file_name for item in discovered] == [
        first_file.name,
        second_file.name,
    ]


def test_single_file_source_rejects_multiple_matches(
    tmp_path: Path,
) -> None:
    first_file = tmp_path / "product_sku_list.xlsx"
    second_directory = tmp_path / "nested"
    second_directory.mkdir()

    first_file.write_bytes(b"sku-master")

    # Path.glob() here is non-recursive, so nested files must not count.
    nested_file = second_directory / "product_sku_list.xlsx"
    nested_file.write_bytes(b"nested")

    discovered = discover_source_files(
        source_name="sku_master",
        input_directory=tmp_path,
    )

    assert len(discovered) == 1
    assert discovered[0].file_name == first_file.name


def test_campaign_overview_returns_multiple_matching_files(
    tmp_path: Path,
) -> None:
    first_file = tmp_path / "Campaign-overview-data-20260701-20260714.xlsx"
    second_file = tmp_path / "Campaign-overview-data-20260715-20260731.xlsx"

    first_file.write_bytes(b"first")
    second_file.write_bytes(b"second")

    discovered = discover_source_files(
        source_name="campaign_overview",
        input_directory=tmp_path,
    )

    assert len(discovered) == 2
    assert [item.file_name for item in discovered] == [
        first_file.name,
        second_file.name,
    ]


def test_discovery_is_non_recursive(
    tmp_path: Path,
) -> None:
    nested_directory = tmp_path / "nested"
    nested_directory.mkdir()

    nested_file = (
        nested_directory
        / "Live Performance Core Stats_20260813053922.xlsx"
    )
    nested_file.write_bytes(b"nested")

    discovered = discover_source_files(
        source_name="live_performance",
        input_directory=tmp_path,
    )

    assert discovered == ()


def test_discover_all_sources_returns_all_registry_sources(
    tmp_path: Path,
) -> None:
    results = discover_all_sources(tmp_path)

    assert set(results) == {
        "orders",
        "shop_analytics",
        "campaign_overview",
        "live_performance",
        "product_card_traffic",
        "product_master",
        "sku_master",
        "influencer_roster",
    }


def test_discover_all_sources_maps_files_to_correct_sources(
    tmp_path: Path,
) -> None:
    order_file = tmp_path / "ทั้งหมด คำสั่งซื้อ-2026-08-13.csv"
    live_file = tmp_path / "Live Performance Core Stats_20260813053922.xlsx"
    sku_file = tmp_path / "product_sku_list.xlsx"

    order_file.write_bytes(b"orders")
    live_file.write_bytes(b"live")
    sku_file.write_bytes(b"sku")

    results = discover_all_sources(tmp_path)

    assert len(results["orders"]) == 1
    assert results["orders"][0].file_name == order_file.name

    assert len(results["live_performance"]) == 1
    assert results["live_performance"][0].file_name == live_file.name

    assert len(results["sku_master"]) == 1
    assert results["sku_master"][0].file_name == sku_file.name

    assert results["shop_analytics"] == ()
    assert results["campaign_overview"] == ()
    assert results["product_card_traffic"] == ()
    assert results["product_master"] == ()