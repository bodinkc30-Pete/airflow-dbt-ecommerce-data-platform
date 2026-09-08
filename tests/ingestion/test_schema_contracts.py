import pytest

from ecommerce_pipeline.ingestion.schema_contracts import (
    SCHEMA_CONTRACTS,
    SchemaContract,
    get_schema_contract,
    list_schema_contract_names,
    validate_schema_contracts,
)
from ecommerce_pipeline.ingestion.source_registry import SOURCE_REGISTRY

EXPECTED_COLUMN_COUNTS = {
    "orders": 65,
    "shop_analytics": 28,
    "campaign_overview": 7,
    "live_performance": 18,
    "product_card_traffic": 16,
    "product_master": 176,
    "sku_master": 7,
}


def test_schema_contract_registry_contains_exactly_seven_sources() -> None:
    assert len(SCHEMA_CONTRACTS) == 7


def test_schema_contract_names_match_source_registry() -> None:
    assert set(SCHEMA_CONTRACTS) == set(SOURCE_REGISTRY)


def test_every_schema_contract_is_schema_contract() -> None:
    for contract in SCHEMA_CONTRACTS.values():
        assert isinstance(contract, SchemaContract)


@pytest.mark.parametrize(
    ("source_name", "expected_column_count"),
    EXPECTED_COLUMN_COUNTS.items(),
)
def test_expected_column_counts_are_correct(
    source_name: str,
    expected_column_count: int,
) -> None:
    contract = get_schema_contract(source_name)

    assert contract.expected_column_count == expected_column_count


def test_product_master_uses_two_level_header_strategy() -> None:
    contract = get_schema_contract("product_master")

    assert contract.header_strategy == "product_master_two_level"


def test_other_sources_use_flat_header_strategy() -> None:
    for source_name, contract in SCHEMA_CONTRACTS.items():
        if source_name == "product_master":
            continue

        assert contract.header_strategy == "flat"


def test_all_schema_contracts_currently_use_strict_drift_policy() -> None:
    for contract in SCHEMA_CONTRACTS.values():
        assert contract.drift_policy == "strict"


def test_required_canonical_names_are_unique_per_source() -> None:
    for contract in SCHEMA_CONTRACTS.values():
        canonical_names = [
            column.canonical_name
            for column in contract.required_columns
        ]

        assert len(canonical_names) == len(set(canonical_names))


def test_required_columns_have_accepted_source_names() -> None:
    for contract in SCHEMA_CONTRACTS.values():
        for column in contract.required_columns:
            assert column.accepted_source_names


def test_required_column_names_are_non_blank() -> None:
    for contract in SCHEMA_CONTRACTS.values():
        for column in contract.required_columns:
            assert column.canonical_name.strip()

            for source_name in column.accepted_source_names:
                assert source_name.strip()


def test_orders_requires_order_id_and_sku_id() -> None:
    contract = get_schema_contract("orders")

    required_names = {
        column.canonical_name
        for column in contract.required_columns
    }

    assert required_names == {
        "order_id",
        "sku_id",
    }


def test_shop_analytics_requires_metric_date() -> None:
    contract = get_schema_contract("shop_analytics")

    required_names = {
        column.canonical_name
        for column in contract.required_columns
    }

    assert required_names == {"metric_date"}


def test_live_performance_requires_metric_date() -> None:
    contract = get_schema_contract("live_performance")

    required_names = {
        column.canonical_name
        for column in contract.required_columns
    }

    assert required_names == {"metric_date"}


def test_live_performance_includes_verified_thai_time_header_alias() -> None:
    contract = get_schema_contract("live_performance")
    required = contract.required_columns[0]

    assert required.canonical_name == "metric_date"
    assert "\u0E40\u0E27\u0E25\u0E32" in required.accepted_source_names



def test_product_card_traffic_requires_metric_date() -> None:
    contract = get_schema_contract("product_card_traffic")

    required_names = {
        column.canonical_name
        for column in contract.required_columns
    }

    assert required_names == {"metric_date"}


def test_product_master_requires_product_id() -> None:
    contract = get_schema_contract("product_master")

    required_names = {
        column.canonical_name
        for column in contract.required_columns
    }

    assert required_names == {"product_id"}


def test_sku_master_requires_sku_id_and_product_id() -> None:
    contract = get_schema_contract("sku_master")

    required_names = {
        column.canonical_name
        for column in contract.required_columns
    }

    assert required_names == {
        "sku_id",
        "product_id",
    }


def test_campaign_overview_requires_verified_metric_date() -> None:
    contract = get_schema_contract("campaign_overview")

    assert len(contract.required_columns) == 1
    required = contract.required_columns[0]

    assert required.canonical_name == "metric_date"
    assert "\u0E15\u0E32\u0E21\u0E27\u0E31\u0E19" in required.accepted_source_names


def test_get_schema_contract_returns_registered_contract() -> None:
    contract = get_schema_contract("orders")

    assert contract is SCHEMA_CONTRACTS["orders"]


def test_get_schema_contract_rejects_unknown_source() -> None:
    with pytest.raises(
        KeyError,
        match="Unknown schema contract 'does_not_exist'",
    ):
        get_schema_contract("does_not_exist")


def test_list_schema_contract_names_is_sorted_and_deterministic() -> None:
    names = list_schema_contract_names()

    assert isinstance(names, tuple)
    assert names == tuple(sorted(SCHEMA_CONTRACTS))


def test_validate_schema_contracts_passes() -> None:
    validate_schema_contracts()