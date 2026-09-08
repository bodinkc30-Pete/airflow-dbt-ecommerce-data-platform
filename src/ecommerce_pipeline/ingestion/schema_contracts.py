from dataclasses import dataclass
from typing import Literal

HeaderStrategy = Literal[
    "flat",
    "product_master_two_level",
]

SchemaDriftPolicy = Literal[
    "strict",
    "allow_additive",
]


@dataclass(frozen=True)
class RequiredColumn:
    canonical_name: str
    accepted_source_names: tuple[str, ...]


@dataclass(frozen=True)
class SchemaContract:
    source_name: str
    expected_column_count: int
    header_strategy: HeaderStrategy
    drift_policy: SchemaDriftPolicy
    required_columns: tuple[RequiredColumn, ...]
    case_sensitive: bool = False
    trim_column_names: bool = True


SCHEMA_CONTRACTS: dict[str, SchemaContract] = {
    "orders": SchemaContract(
        source_name="orders",
        expected_column_count=65,
        header_strategy="flat",
        drift_policy="strict",
        required_columns=(
            RequiredColumn(
                canonical_name="order_id",
                accepted_source_names=(
                    "Order ID",
                    "order_id",
                ),
            ),
            RequiredColumn(
                canonical_name="sku_id",
                accepted_source_names=(
                    "SKU ID",
                    "sku_id",
                ),
            ),
        ),
    ),
    "shop_analytics": SchemaContract(
        source_name="shop_analytics",
        expected_column_count=28,
        header_strategy="flat",
        drift_policy="strict",
        required_columns=(
            RequiredColumn(
                canonical_name="metric_date",
                accepted_source_names=(
                    "Date",
                    "date",
                    "Metric Date",
                    "metric_date",
                    "\u0E27\u0E31\u0E19\u0E17\u0E35\u0E48",
                ),
            ),
        ),
    ),
    "campaign_overview": SchemaContract(
        source_name="campaign_overview",
        expected_column_count=7,
        header_strategy="flat",
        drift_policy="strict",
        required_columns=(
            RequiredColumn(
                canonical_name="metric_date",
                accepted_source_names=(
                    "Date",
                    "date",
                    "Metric Date",
                    "metric_date",
                    "\u0E15\u0E32\u0E21\u0E27\u0E31\u0E19",
                ),
            ),
        ),
    ),
    "live_performance": SchemaContract(
        source_name="live_performance",
        expected_column_count=18,
        header_strategy="flat",
        drift_policy="strict",
        required_columns=(
            RequiredColumn(
                canonical_name="metric_date",
                accepted_source_names=(
                    "Date",
                    "date",
                    "Metric Date",
                    "metric_date",
                    "\u0E40\u0E27\u0E25\u0E32",
                ),
            ),
        ),
    ),
    "product_card_traffic": SchemaContract(
        source_name="product_card_traffic",
        expected_column_count=16,
        header_strategy="flat",
        drift_policy="strict",
        required_columns=(
            RequiredColumn(
                canonical_name="metric_date",
                accepted_source_names=(
                    "Date",
                    "date",
                    "Metric Date",
                    "metric_date",
                    "\u0E40\u0E27\u0E25\u0E32",
                ),
            ),
        ),
    ),
    "product_master": SchemaContract(
        source_name="product_master",
        expected_column_count=176,
        header_strategy="product_master_two_level",
        drift_policy="strict",
        required_columns=(
            RequiredColumn(
                canonical_name="product_id",
                accepted_source_names=(
                    "Product ID",
                    "product_id",
                    "\u0E23\u0E2B\u0E31\u0E2A\u0E2A\u0E34\u0E19\u0E04\u0E49\u0E32",
                ),
            ),
        ),
    ),
    "sku_master": SchemaContract(
        source_name="sku_master",
        expected_column_count=7,
        header_strategy="flat",
        drift_policy="strict",
        required_columns=(
            RequiredColumn(
                canonical_name="sku_id",
                accepted_source_names=(
                    "SKU ID",
                    "sku_id",
                ),
            ),
            RequiredColumn(
                canonical_name="product_id",
                accepted_source_names=(
                    "Product ID",
                    "product_id",
                ),
            ),
        ),
    ),
    "influencer_roster": SchemaContract(
        source_name="influencer_roster",
        expected_column_count=12,
        header_strategy="flat",
        drift_policy="strict",
        required_columns=(
            RequiredColumn(
                canonical_name="influencer_name",
                accepted_source_names=("Influencer",),
            ),
            RequiredColumn(
                canonical_name="follower_count",
                accepted_source_names=("Follower",),
            ),
            RequiredColumn(
                canonical_name="engagement_rate",
                accepted_source_names=("Engangement Rate%",),
            ),
            RequiredColumn(
                canonical_name="budget",
                accepted_source_names=("BUDGET",),
            ),
        ),
    ),
}


def get_schema_contract(source_name: str) -> SchemaContract:
    try:
        return SCHEMA_CONTRACTS[source_name]
    except KeyError as exc:
        available = ", ".join(sorted(SCHEMA_CONTRACTS))
        raise KeyError(
            f"Unknown schema contract '{source_name}'. "
            f"Available sources: {available}"
        ) from exc


def list_schema_contract_names() -> tuple[str, ...]:
    return tuple(sorted(SCHEMA_CONTRACTS))


def validate_schema_contracts() -> None:
    if len(SCHEMA_CONTRACTS) != 8:
        raise ValueError(
            "Schema contract registry must contain exactly 8 sources"
        )

    for registry_name, contract in SCHEMA_CONTRACTS.items():
        if registry_name != contract.source_name:
            raise ValueError(
                "Schema contract registry key does not match "
                f"source_name: {registry_name}"
            )

        if contract.expected_column_count <= 0:
            raise ValueError(
                f"Source '{registry_name}' must define a positive "
                "expected_column_count"
            )

        canonical_names = [
            column.canonical_name
            for column in contract.required_columns
        ]

        if len(canonical_names) != len(set(canonical_names)):
            raise ValueError(
                f"Source '{registry_name}' contains duplicate "
                "required canonical column names"
            )

        for required_column in contract.required_columns:
            if not required_column.canonical_name.strip():
                raise ValueError(
                    f"Source '{registry_name}' contains a blank "
                    "canonical column name"
                )

            if not required_column.accepted_source_names:
                raise ValueError(
                    f"Required column "
                    f"'{required_column.canonical_name}' for source "
                    f"'{registry_name}' has no accepted source names"
                )

            if any(
                not source_name.strip()
                for source_name
                in required_column.accepted_source_names
            ):
                raise ValueError(
                    f"Required column "
                    f"'{required_column.canonical_name}' for source "
                    f"'{registry_name}' contains a blank source name"
                )


validate_schema_contracts()