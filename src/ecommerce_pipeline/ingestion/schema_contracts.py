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
                ),
            ),
        ),
    ),
    "campaign_overview": SchemaContract(
        source_name="campaign_overview",
        expected_column_count=7,
        header_strategy="flat",
        drift_policy="strict",
        required_columns=(),
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
    if len(SCHEMA_CONTRACTS) != 7:
        raise ValueError(
            "Schema contract registry must contain exactly 7 sources"
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