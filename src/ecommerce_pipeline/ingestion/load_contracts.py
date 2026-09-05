from collections.abc import Mapping
from dataclasses import dataclass

_CURRENT_SHOP_SUFFIX = (
    " (\u0E23\u0E49\u0E32\u0E19\u0E04\u0E49\u0E32"
    "\u0E1B\u0E31\u0E08\u0E08\u0E38\u0E1A\u0E31\u0E19)"
)

_CAMPAIGN_DATE_HEADER = "\u0E15\u0E32\u0E21\u0E27\u0E31\u0E19"
_CAMPAIGN_AD_COST_HEADER = "\u0E15\u0E49\u0E19\u0E17\u0E38\u0E19"
_CAMPAIGN_SKU_ORDERS_HEADER = (
    "\u0E04\u0E33\u0E2A\u0E31\u0E48\u0E07"
    "\u0E0B\u0E37\u0E49\u0E2D SKU"
    + _CURRENT_SHOP_SUFFIX
)
_CAMPAIGN_COST_PER_ORDER_HEADER = (
    "\u0E04\u0E48\u0E32\u0E43\u0E0A\u0E49"
    "\u0E08\u0E48\u0E32\u0E22\u0E15\u0E48\u0E2D"
    "\u0E04\u0E33\u0E2A\u0E31\u0E48\u0E07"
    "\u0E0B\u0E37\u0E49\u0E2D"
    + _CURRENT_SHOP_SUFFIX
)
_CAMPAIGN_GROSS_REVENUE_HEADER = (
    "\u0E23\u0E32\u0E22\u0E44\u0E14\u0E49"
    "\u0E02\u0E31\u0E49\u0E19\u0E15\u0E49\u0E19"
    + _CURRENT_SHOP_SUFFIX
)
_CAMPAIGN_ROI_HEADER = "ROI" + _CURRENT_SHOP_SUFFIX
_CAMPAIGN_CURRENCY_HEADER = "\u0E2A\u0E01\u0E38\u0E25\u0E40\u0E07\u0E34\u0E19"


@dataclass(frozen=True)
class LoadContract:
    source_name: str
    column_mapping: Mapping[str, str]


LOAD_CONTRACTS: dict[str, LoadContract] = {
    "campaign_overview": LoadContract(
        source_name="campaign_overview",
        column_mapping={
            _CAMPAIGN_DATE_HEADER: "metric_date",
            _CAMPAIGN_AD_COST_HEADER: "ad_cost",
            _CAMPAIGN_SKU_ORDERS_HEADER: "sku_orders",
            _CAMPAIGN_COST_PER_ORDER_HEADER: "cost_per_order",
            _CAMPAIGN_GROSS_REVENUE_HEADER: "gross_revenue",
            _CAMPAIGN_ROI_HEADER: "roi",
            _CAMPAIGN_CURRENCY_HEADER: "currency",
        },
    ),
}


def get_load_contract(source_name: str) -> LoadContract:
    try:
        return LOAD_CONTRACTS[source_name]
    except KeyError as exc:
        available = ", ".join(sorted(LOAD_CONTRACTS))
        raise KeyError(
            f"Unknown load contract '{source_name}'. "
            f"Available sources: {available}"
        ) from exc


def list_load_contract_names() -> tuple[str, ...]:
    return tuple(sorted(LOAD_CONTRACTS))


def validate_load_contracts() -> None:
    for registry_name, contract in LOAD_CONTRACTS.items():
        if registry_name != contract.source_name:
            raise ValueError(
                "Load contract registry key does not match "
                f"source_name: {registry_name}"
            )

        if not contract.column_mapping:
            raise ValueError(
                f"Source '{registry_name}' must define a column mapping"
            )

        if any(
            not source_column.strip()
            for source_column in contract.column_mapping
        ):
            raise ValueError(
                f"Source '{registry_name}' contains a blank source column"
            )

        destination_columns = tuple(contract.column_mapping.values())

        if any(
            not destination_column.strip()
            for destination_column in destination_columns
        ):
            raise ValueError(
                f"Source '{registry_name}' contains a blank "
                "destination column"
            )

        if len(destination_columns) != len(set(destination_columns)):
            raise ValueError(
                f"Source '{registry_name}' contains duplicate "
                "destination columns"
            )


validate_load_contracts()
