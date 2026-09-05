from ecommerce_pipeline.ingestion.load_contracts import (
    LOAD_CONTRACTS,
    get_load_contract,
    list_load_contract_names,
    validate_load_contracts,
)


def test_campaign_load_contract_contains_verified_seven_column_mapping() -> None:
    current_shop_suffix = (
        " (\u0E23\u0E49\u0E32\u0E19\u0E04\u0E49\u0E32"
        "\u0E1B\u0E31\u0E08\u0E08\u0E38\u0E1A\u0E31\u0E19)"
    )

    expected_mapping = {
        "\u0E15\u0E32\u0E21\u0E27\u0E31\u0E19": "metric_date",
        "\u0E15\u0E49\u0E19\u0E17\u0E38\u0E19": "ad_cost",
        (
            "\u0E04\u0E33\u0E2A\u0E31\u0E48\u0E07"
            "\u0E0B\u0E37\u0E49\u0E2D SKU"
            + current_shop_suffix
        ): "sku_orders",
        (
            "\u0E04\u0E48\u0E32\u0E43\u0E0A\u0E49"
            "\u0E08\u0E48\u0E32\u0E22\u0E15\u0E48\u0E2D"
            "\u0E04\u0E33\u0E2A\u0E31\u0E48\u0E07"
            "\u0E0B\u0E37\u0E49\u0E2D"
            + current_shop_suffix
        ): "cost_per_order",
        (
            "\u0E23\u0E32\u0E22\u0E44\u0E14\u0E49"
            "\u0E02\u0E31\u0E49\u0E19\u0E15\u0E49\u0E19"
            + current_shop_suffix
        ): "gross_revenue",
        ("ROI" + current_shop_suffix): "roi",
        "\u0E2A\u0E01\u0E38\u0E25\u0E40\u0E07\u0E34\u0E19": "currency",
    }

    contract = get_load_contract("campaign_overview")

    assert contract.source_name == "campaign_overview"
    assert contract.column_mapping == expected_mapping


def test_campaign_load_contract_destination_columns_are_unique() -> None:
    contract = get_load_contract("campaign_overview")

    destinations = tuple(contract.column_mapping.values())

    assert len(destinations) == 7
    assert len(destinations) == len(set(destinations))


def test_only_verified_load_contracts_are_registered() -> None:
    assert set(LOAD_CONTRACTS) == {"campaign_overview"}
    assert list_load_contract_names() == ("campaign_overview",)


def test_validate_load_contracts_passes() -> None:
    validate_load_contracts()
