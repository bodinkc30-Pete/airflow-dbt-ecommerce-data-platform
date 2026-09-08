import pytest

from ecommerce_pipeline.ingestion.source_registry import (
    SOURCE_REGISTRY,
    SourceConfig,
    get_source_config,
    list_source_names,
    validate_source_registry,
)

EXPECTED_SOURCES = {
    "orders",
    "shop_analytics",
    "campaign_overview",
    "live_performance",
    "product_card_traffic",
    "product_master",
    "sku_master",
    "influencer_roster",
}


EXPECTED_TARGET_TABLES = {
    "orders": "raw.orders",
    "shop_analytics": "raw.shop_daily",
    "campaign_overview": "raw.campaign_daily",
    "live_performance": "raw.live_daily",
    "product_card_traffic": "raw.product_card_daily",
    "product_master": "raw.products",
    "sku_master": "raw.skus",
    "influencer_roster": "raw.influencer_roster",
}


def test_registry_contains_exactly_eight_sources() -> None:
    assert len(SOURCE_REGISTRY) == 8
    assert set(SOURCE_REGISTRY) == EXPECTED_SOURCES


def test_every_registry_value_is_source_config() -> None:
    for config in SOURCE_REGISTRY.values():
        assert isinstance(config, SourceConfig)


def test_source_ids_are_unique() -> None:
    source_ids = [
        config.source_id
        for config in SOURCE_REGISTRY.values()
    ]

    assert len(source_ids) == len(set(source_ids))


def test_target_tables_are_unique() -> None:
    target_tables = [
        config.target_table
        for config in SOURCE_REGISTRY.values()
    ]

    assert len(target_tables) == len(set(target_tables))


@pytest.mark.parametrize(
    ("source_name", "expected_target"),
    EXPECTED_TARGET_TABLES.items(),
)
def test_source_maps_to_expected_raw_table(
    source_name: str,
    expected_target: str,
) -> None:
    config = get_source_config(source_name)

    assert config.target_table == expected_target


def test_get_source_config_returns_registered_config() -> None:
    config = get_source_config("orders")

    assert config is SOURCE_REGISTRY["orders"]
    assert config.source_id == "SRC_ORDERS"
    assert config.load_strategy == "incremental"


def test_get_source_config_rejects_unknown_source() -> None:
    with pytest.raises(KeyError, match="Unknown source 'does_not_exist'"):
        get_source_config("does_not_exist")


def test_list_source_names_is_deterministic_and_sorted() -> None:
    source_names = list_source_names()

    assert isinstance(source_names, tuple)
    assert source_names == tuple(sorted(EXPECTED_SOURCES))


def test_all_target_tables_use_raw_schema() -> None:
    for config in SOURCE_REGISTRY.values():
        assert config.target_table.startswith("raw.")


def test_all_contract_paths_use_source_contract_directory() -> None:
    for config in SOURCE_REGISTRY.values():
        assert config.contract_path.startswith(
            "docs/source_contracts/"
        )
        assert config.contract_path.endswith(
            "_source_contract.md"
        )


def test_all_sources_have_business_keys() -> None:
    for config in SOURCE_REGISTRY.values():
        assert config.business_key


def test_all_sources_preserve_source_text() -> None:
    for config in SOURCE_REGISTRY.values():
        assert config.preserve_source_text is True


def test_incremental_sources_are_configured_correctly() -> None:
    expected_incremental = {
        "orders",
        "shop_analytics",
        "campaign_overview",
        "live_performance",
        "product_card_traffic",
    }

    actual_incremental = {
        source_name
        for source_name, config in SOURCE_REGISTRY.items()
        if config.load_strategy == "incremental"
    }

    assert actual_incremental == expected_incremental


def test_snapshot_sources_are_configured_correctly() -> None:
    expected_snapshot = {
        "product_master",
        "sku_master",
        "influencer_roster",
    }

    actual_snapshot = {
        source_name
        for source_name, config in SOURCE_REGISTRY.items()
        if config.load_strategy == "snapshot"
    }

    assert actual_snapshot == expected_snapshot


def test_excel_sources_have_sheet_names() -> None:
    for config in SOURCE_REGISTRY.values():
        if config.file_format == "xlsx":
            assert config.sheet_name


def test_header_rows_are_non_negative() -> None:
    for config in SOURCE_REGISTRY.values():
        assert config.header_row >= 0


def test_validate_source_registry_passes() -> None:
    validate_source_registry()