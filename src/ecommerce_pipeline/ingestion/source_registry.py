from dataclasses import dataclass
from typing import Literal

FileFormat = Literal["csv", "xlsx"]
LoadStrategy = Literal["incremental", "snapshot"]


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    source_name: str
    domain: str

    file_pattern: str
    file_format: FileFormat

    target_table: str
    contract_path: str

    load_strategy: LoadStrategy

    sheet_name: str | None = None
    header_row: int = 0

    expected_grain: str = ""
    business_key: tuple[str, ...] = ()

    preserve_source_text: bool = True
    supports_multiple_files: bool = False
    supports_late_arriving_data: bool = False


SOURCE_REGISTRY: dict[str, SourceConfig] = {
    "orders": SourceConfig(
        source_id="SRC_ORDERS",
        source_name="orders",
        domain="Orders",
        file_pattern="*คำสั่งซื้อ*.csv",
        file_format="csv",
        target_table="raw.orders",
        contract_path="docs/source_contracts/01_orders_source_contract.md",
        load_strategy="incremental",
        header_row=0,
        expected_grain="one row per order-SKU line",
        business_key=("order_id", "sku_id"),
        preserve_source_text=True,
        supports_multiple_files=True,
        supports_late_arriving_data=True,
    ),
    "shop_analytics": SourceConfig(
        source_id="SRC_SHOP_ANALYTICS",
        source_name="shop_analytics",
        domain="Shop Analytics",
        file_pattern="Shop-Analytics_Key-metrics_*.xlsx",
        file_format="xlsx",
        target_table="raw.shop_daily",
        contract_path="docs/source_contracts/02_shop_analytics_source_contract.md",
        load_strategy="incremental",
        sheet_name="Sheet1",
        header_row=8,
        expected_grain="one row per shop performance day",
        business_key=("metric_date",),
        preserve_source_text=True,
        supports_multiple_files=True,
        supports_late_arriving_data=True,
    ),
    "campaign_overview": SourceConfig(
        source_id="SRC_CAMPAIGN_OVERVIEW",
        source_name="campaign_overview",
        domain="Campaign Performance",
        file_pattern="Campaign-overview-data-*.xlsx",
        file_format="xlsx",
        target_table="raw.campaign_daily",
        contract_path="docs/source_contracts/03_campaign_overview_source_contract.md",
        load_strategy="incremental",
        sheet_name="Sheet1",
        header_row=0,
        expected_grain="one row per shop-level advertising performance day",
        business_key=("metric_date",),
        preserve_source_text=True,
        supports_multiple_files=True,
        supports_late_arriving_data=True,
    ),
    "live_performance": SourceConfig(
        source_id="SRC_LIVE_PERFORMANCE",
        source_name="live_performance",
        domain="LIVE Commerce",
        file_pattern="Live Performance Core Stats_*.xlsx",
        file_format="xlsx",
        target_table="raw.live_daily",
        contract_path="docs/source_contracts/04_live_performance_source_contract.md",
        load_strategy="incremental",
        sheet_name="Sheet1",
        header_row=2,
        expected_grain="one row per LIVE performance day",
        business_key=("metric_date",),
        preserve_source_text=True,
        supports_multiple_files=True,
        supports_late_arriving_data=True,
    ),
    "product_card_traffic": SourceConfig(
        source_id="SRC_PRODUCT_CARD_TRAFFIC",
        source_name="product_card_traffic",
        domain="Product Traffic / Conversion",
        file_pattern="Product Card Traffic Stats_*.xlsx",
        file_format="xlsx",
        target_table="raw.product_card_daily",
        contract_path="docs/source_contracts/05_product_card_traffic_source_contract.md",
        load_strategy="incremental",
        sheet_name="Sheet1",
        header_row=2,
        expected_grain="one row per shop-level Product Card traffic day",
        business_key=("metric_date",),
        preserve_source_text=True,
        supports_multiple_files=True,
        supports_late_arriving_data=True,
    ),
    "product_master": SourceConfig(
        source_id="SRC_PRODUCT_MASTER",
        source_name="product_master",
        domain="Product Master",
        file_pattern="product_list_*.xlsx",
        file_format="xlsx",
        target_table="raw.products",
        contract_path="docs/source_contracts/06_product_master_source_contract.md",
        load_strategy="snapshot",
        sheet_name="Sheet1",
        header_row=3,
        expected_grain="one row per product snapshot record",
        business_key=("product_id",),
        preserve_source_text=True,
        supports_multiple_files=True,
        supports_late_arriving_data=False,
    ),
    "sku_master": SourceConfig(
        source_id="SRC_SKU_MASTER",
        source_name="sku_master",
        domain="SKU Master",
        file_pattern="product_sku_list.xlsx",
        file_format="xlsx",
        target_table="raw.skus",
        contract_path="docs/source_contracts/07_sku_master_source_contract.md",
        load_strategy="snapshot",
        sheet_name="Sheet1",
        header_row=2,
        expected_grain="one row per SKU snapshot record",
        business_key=("sku_id",),
        preserve_source_text=True,
        supports_multiple_files=True,
        supports_late_arriving_data=False,
    ),
    "influencer_roster": SourceConfig(
        source_id="SRC_INFLUENCER_ROSTER",
        source_name="influencer_roster",
        domain="Influencer / Creator Operations",
        file_pattern="influencer_data.csv",
        file_format="csv",
        target_table="raw.influencer_roster",
        contract_path="docs/source_contracts/08_influencer_roster_source_contract.md",
        load_strategy="snapshot",
        header_row=0,
        expected_grain="one influencer roster export row",
        business_key=("influencer_name",),
        preserve_source_text=True,
        supports_multiple_files=False,
        supports_late_arriving_data=False,
    ),
}


def get_source_config(source_name: str) -> SourceConfig:
    """Return one registered source configuration."""

    try:
        return SOURCE_REGISTRY[source_name]
    except KeyError as exc:
        available_sources = ", ".join(sorted(SOURCE_REGISTRY))
        raise KeyError(
            f"Unknown source '{source_name}'. "
            f"Available sources: {available_sources}"
        ) from exc


def list_source_names() -> tuple[str, ...]:
    """Return all registered source names in deterministic order."""

    return tuple(sorted(SOURCE_REGISTRY))


def validate_source_registry() -> None:
    """Validate invariants that every registry entry must satisfy."""

    if len(SOURCE_REGISTRY) != 8:
        raise ValueError(
            f"Expected 8 registered sources, found {len(SOURCE_REGISTRY)}"
        )

    source_ids: set[str] = set()
    target_tables: set[str] = set()

    for registry_key, config in SOURCE_REGISTRY.items():
        if registry_key != config.source_name:
            raise ValueError(
                f"Registry key '{registry_key}' does not match "
                f"source_name '{config.source_name}'"
            )

        if not config.source_id.strip():
            raise ValueError(f"{registry_key}: source_id must not be blank")

        if config.source_id in source_ids:
            raise ValueError(
                f"Duplicate source_id detected: {config.source_id}"
            )

        source_ids.add(config.source_id)

        if not config.file_pattern.strip():
            raise ValueError(
                f"{registry_key}: file_pattern must not be blank"
            )

        if not config.target_table.startswith("raw."):
            raise ValueError(
                f"{registry_key}: target_table must use raw schema"
            )

        if config.target_table in target_tables:
            raise ValueError(
                f"Duplicate target_table detected: {config.target_table}"
            )

        target_tables.add(config.target_table)

        if not config.contract_path.startswith("docs/source_contracts/"):
            raise ValueError(
                f"{registry_key}: invalid contract_path"
            )

        if not config.business_key:
            raise ValueError(
                f"{registry_key}: business_key must not be empty"
            )

        if config.header_row < 0:
            raise ValueError(
                f"{registry_key}: header_row must be >= 0"
            )


validate_source_registry()