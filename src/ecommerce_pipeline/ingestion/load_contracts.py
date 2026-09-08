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


_ORDERS_COLUMN_MAPPING = {
    "Order ID": "order_id",
    "Order Status": "order_status",
    "Order Substatus": "order_substatus",
    "Cancelation/Return Type": "cancelation_return_type",
    "Normal or Pre-order": "normal_or_pre_order",
    "SKU ID": "sku_id",
    "Seller SKU": "seller_sku",
    "Product Name": "product_name",
    "Variation": "variation",
    "Quantity": "quantity",
    "Sku Quantity of return": "sku_quantity_of_return",
    "SKU Unit Original Price": "sku_unit_original_price",
    "SKU Subtotal Before Discount": "sku_subtotal_before_discount",
    "SKU Platform Discount": "sku_platform_discount",
    "SKU Seller Discount": "sku_seller_discount",
    "SKU Subtotal After Discount": "sku_subtotal_after_discount",
    "Shipping Fee After Discount": "shipping_fee_after_discount",
    "Original Shipping Fee": "original_shipping_fee",
    "Shipping Fee Seller Discount": "shipping_fee_seller_discount",
    "Shipping Fee Platform Discount": "shipping_fee_platform_discount",
    "Payment platform discount": "payment_platform_discount",
    "Taxes": "taxes",
    "Order Amount": "order_amount",
    "Order Refund Amount": "order_refund_amount",
    "Created Time": "created_time",
    "Paid Time": "paid_time",
    "RTS Time": "rts_time",
    "Shipped Time": "shipped_time",
    "Delivered Time": "delivered_time",
    "Cancelled Time": "cancelled_time",
    "Cancel By": "cancel_by",
    "Cancel Reason": "cancel_reason",
    "Fulfillment Type": "fulfillment_type",
    "Warehouse Name": "warehouse_name",
    "Tracking ID": "tracking_id",
    "Delivery Option": "delivery_option",
    "Shipping Provider Name": "shipping_provider_name",
    "Buyer Message": "buyer_message",
    "Buyer Username": "buyer_username",
    "Recipient": "recipient",
    "Phone #": "phone_number",
    "Zipcode": "zipcode",
    "Country": "country",
    "Province": "province",
    "District": "district",
    "Districts": "districts",
    "Detail Address": "detail_address",
    "Additional address information": "additional_address_information",
    "Payment Method": "payment_method",
    "Weight(kg)": "weight_kg",
    "Product Category": "product_category",
    "Package ID": "package_id",
    "Seller Note": "seller_note",
    "Checked Status": "checked_status",
    "Checked Marked by": "checked_marked_by",
    "Order Channel": "order_channel",
    "Creator Handle": "creator_handle",
    "Request Tax Invoice": "request_tax_invoice",
    "Tax Info - Buyer Tax ID": "tax_info_buyer_tax_id",
    "Tax Info - Type": "tax_info_type",
    "Tax Info - Full Name of Buyer": "tax_info_full_name_of_buyer",
    "Tax Info - Email": "tax_info_email",
    "Tax Info - Phone Number": "tax_info_phone_number",
    "Tax Info - Registered Address": "tax_info_registered_address",
    "Tax Info - Address Type": "tax_info_address_type",
}


_LIVE_PERFORMANCE_COLUMN_MAPPING = {
    "\u0e40\u0e27\u0e25\u0e32": "metric_date",
    (
        "GMV \u0e17\u0e35\u0e48\u0e21"
        "\u0e32\u0e08\u0e32\u0e01 LIV"
        "E (\u0e3f)"
    ): "live_attributed_gmv",
    (
        "GMV \u0e08\u0e32\u0e01 "
        "LIVE (\u0e3f)"
    ): "live_direct_gmv",
    (
        "GMV \u0e42\u0e14\u0e22\u0e2d"
        "\u0e49\u0e2d\u0e21\u0e08\u0e32\u0e01 L"
        "IVE (\u0e3f)"
    ): "live_indirect_gmv",
    (
        "\u0e41\u0e2a\u0e14\u0e07 GPM"
        " (\u0e3f)"
    ): "display_gpm",
    (
        "\u0e44\u0e25\u0e1f\u0e4c\u0e2a\u0e15\u0e23\u0e35"
        "\u0e21"
    ): "live_stream_count",
    (
        "\u0e08\u0e33\u0e19\u0e27\u0e19\u0e44\u0e25\u0e1f"
        "\u0e4c\u0e2a\u0e15\u0e23\u0e35\u0e21\u0e17\u0e35"
        "\u0e48\u0e2a\u0e23\u0e49\u0e32\u0e07 G"
        "MV \u0e44\u0e14\u0e49"
    ): "gmv_generating_live_stream_count",
    (
        "\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32\u0e17\u0e35"
        "\u0e48\u0e02\u0e32\u0e22\u0e44\u0e14\u0e49\u0e17"
        "\u0e35\u0e48\u0e19\u0e31\u0e1a\u0e22\u0e2d\u0e14"
        "\u0e43\u0e2b\u0e49 LIVE"
    ): "live_attributed_items_sold",
    (
        "\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32\u0e17\u0e35"
        "\u0e48\u0e02\u0e32\u0e22\u0e44\u0e14\u0e49\u0e08"
        "\u0e32\u0e01 LIVE"
    ): "live_direct_items_sold",
    (
        "\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32\u0e17\u0e35"
        "\u0e48\u0e02\u0e32\u0e22\u0e44\u0e14\u0e49\u0e42"
        "\u0e14\u0e22\u0e2d\u0e49\u0e2d\u0e21\u0e08\u0e32"
        "\u0e01 LIVE"
    ): "live_indirect_items_sold",
    (
        "\u0e04\u0e33\u0e2a\u0e31\u0e48\u0e07\u0e0b\u0e37"
        "\u0e49\u0e2d SKU \u0e08"
        "\u0e32\u0e01\u0e41\u0e2b\u0e25\u0e48\u0e07\u0e17"
        "\u0e35\u0e48\u0e21\u0e32"
    ): "attributed_sku_orders",
    (
        "\u0e04\u0e33\u0e2a\u0e31\u0e48\u0e07\u0e0b\u0e37"
        "\u0e49\u0e2d SKU \u0e08"
        "\u0e32\u0e01 LIVE"
    ): "live_direct_sku_orders",
    (
        "\u0e04\u0e33\u0e2a\u0e31\u0e48\u0e07\u0e0b\u0e37"
        "\u0e49\u0e2d SKU \u0e42"
        "\u0e14\u0e22\u0e2d\u0e49\u0e2d\u0e21\u0e08\u0e32"
        "\u0e01 LIVE"
    ): "live_indirect_sku_orders",
    (
        "\u0e25\u0e39\u0e01\u0e04\u0e49\u0e32 ("
        "\u0e01\u0e32\u0e23\u0e04\u0e49\u0e19\u0e2b\u0e32"
        ")"
    ): "customers_search",
    (
        "\u0e2d\u0e31\u0e15\u0e23\u0e32\u0e01\u0e32\u0e23"
        "\u0e04\u0e25\u0e34\u0e01\u0e1c\u0e48\u0e32\u0e19"
        " (LIVE)"
    ): "live_click_through_rate",
    (
        "CTOR (\u0e04\u0e33"
        "\u0e2a\u0e31\u0e48\u0e07\u0e0b\u0e37\u0e49\u0e2d"
        " SKU) (L"
        "IVE)"
    ): "live_sku_order_ctor",
    (
        "\u0e22\u0e2d\u0e14\u0e01\u0e32\u0e23\u0e14\u0e39"
        "\u0e44\u0e25\u0e1f\u0e4c"
    ): "live_views",
    (
        "\u0e23\u0e30\u0e22\u0e30\u0e40\u0e27\u0e25\u0e32"
        "\u0e01\u0e32\u0e23\u0e14\u0e39\u0e42\u0e14\u0e22"
        "\u0e40\u0e09\u0e25\u0e35\u0e48\u0e22 ("
        "\u0e44\u0e25\u0e1f\u0e4c\u0e2a\u0e15\u0e23\u0e35"
        "\u0e21)"
    ): "average_live_watch_duration",
}

_SHOP_ANALYTICS_COLUMN_MAPPING = {
    "\u0e27\u0e31\u0e19\u0e17\u0e35\u0e48": "metric_date",
    "GMV": "gmv",
    "\u0e04\u0e33\u0e2a\u0e31\u0e48\u0e07\u0e0b\u0e37\u0e49\u0e2d": "orders",
    "\u0e25\u0e39\u0e01\u0e04\u0e49\u0e32": "customers",
    (
        "\u0e2a\u0e34\u0e19\u0e04\u0e49\u0e32\u0e17\u0e35"
        "\u0e48\u0e02\u0e32\u0e22\u0e44\u0e14\u0e49"
    ): "items_sold",
    (
        "\u0e23\u0e32\u0e22\u0e01\u0e32\u0e23\u0e17\u0e35"
        "\u0e48\u0e21\u0e35\u0e01\u0e32\u0e23\u0e04\u0e37"
        "\u0e19\u0e40\u0e07\u0e34\u0e19"
    ): "refunds",
    "\u0e04\u0e33\u0e2a\u0e31\u0e48\u0e07\u0e0b\u0e37\u0e49\u0e2d SKU": "sku_orders",
    "\u0e23\u0e32\u0e22\u0e44\u0e14\u0e49\u0e23\u0e27\u0e21": "gross_revenue",
    (
        "\u0e22\u0e2d\u0e14\u0e01\u0e32\u0e23\u0e14\u0e39"
        "\u0e2b\u0e19\u0e49\u0e32\u0e40\u0e27\u0e47\u0e1a"
    ): "page_views",
    "\u0e1c\u0e39\u0e49\u0e40\u0e02\u0e49\u0e32\u0e0a\u0e21": "visitors",
    (
        "\u0e2d\u0e31\u0e15\u0e23\u0e32\u0e04\u0e2d\u0e19"
        "\u0e40\u0e27\u0e2d\u0e23\u0e4c\u0e0a\u0e31\u0e48"
        "\u0e19"
    ): "conversion_rate",
    (
        "\u0e22\u0e2d\u0e14\u0e01\u0e32\u0e23\u0e41\u0e2a"
        "\u0e14\u0e07\u0e1c\u0e25\u0e2a\u0e34\u0e19\u0e04"
        "\u0e49\u0e32"
    ): "product_impressions",
    (
        "\u0e22\u0e2d\u0e14\u0e01\u0e32\u0e23\u0e41\u0e2a"
        "\u0e14\u0e07\u0e1c\u0e25\u0e2a\u0e34\u0e19\u0e04"
        "\u0e49\u0e32\u0e17\u0e35\u0e48\u0e44\u0e21\u0e48"
        "\u0e0b\u0e49\u0e33\u0e01\u0e31\u0e19"
    ): "unique_product_impressions",
    (
        "\u0e22\u0e2d\u0e14\u0e04\u0e25\u0e34\u0e01\u0e2a"
        "\u0e34\u0e19\u0e04\u0e49\u0e32"
    ): "product_clicks",
    (
        "\u0e22\u0e2d\u0e14\u0e04\u0e25\u0e34\u0e01\u0e17"
        "\u0e35\u0e48\u0e44\u0e21\u0e48\u0e0b\u0e49\u0e33"
        "\u0e01\u0e31\u0e19"
    ): "unique_product_clicks",
    "AOV": "aov",
    (
        "GMV \u0e17\u0e35\u0e48\u0e21"
        "\u0e32\u0e08\u0e32\u0e01 LIV"
        "E \u0e02\u0e2d\u0e07\u0e04\u0e23\u0e35"
        "\u0e40\u0e2d\u0e40\u0e15\u0e2d\u0e23\u0e4c"
    ): "creator_live_attributed_gmv",
    (
        "GMV \u0e08\u0e32\u0e01 "
        "LIVE \u0e02\u0e2d\u0e07"
        "\u0e04\u0e23\u0e35\u0e40\u0e2d\u0e40\u0e15\u0e2d"
        "\u0e23\u0e4c"
    ): "creator_live_direct_gmv",
    (
        "GMV \u0e42\u0e14\u0e22\u0e2d"
        "\u0e49\u0e2d\u0e21\u0e08\u0e32\u0e01 L"
        "IVE \u0e02\u0e2d\u0e07\u0e04"
        "\u0e23\u0e35\u0e40\u0e2d\u0e40\u0e15\u0e2d\u0e23"
        "\u0e4c"
    ): "creator_live_indirect_gmv",
    (
        "GMV \u0e08\u0e32\u0e01 "
        "LIVE \u0e02\u0e2d\u0e07"
        "\u0e1a\u0e31\u0e0d\u0e0a\u0e35\u0e17\u0e35\u0e48"
        "\u0e40\u0e0a\u0e37\u0e48\u0e2d\u0e21\u0e42\u0e22"
        "\u0e07"
    ): "linked_account_live_gmv",
    (
        "GMV \u0e08\u0e32\u0e01 "
        "LIVE \u0e02\u0e2d\u0e07"
        "\u0e1c\u0e39\u0e49\u0e02\u0e32\u0e22"
    ): "seller_live_direct_gmv",
    (
        "GMV \u0e42\u0e14\u0e22\u0e2d"
        "\u0e49\u0e2d\u0e21\u0e08\u0e32\u0e01 L"
        "IVE \u0e02\u0e2d\u0e07\u0e1c"
        "\u0e39\u0e49\u0e02\u0e32\u0e22"
    ): "seller_live_indirect_gmv",
    (
        "GMV \u0e17\u0e35\u0e48\u0e21"
        "\u0e32\u0e08\u0e32\u0e01\u0e27\u0e34\u0e14\u0e35"
        "\u0e42\u0e2d\u0e02\u0e2d\u0e07\u0e41\u0e2d\u0e1f"
        "\u0e1f\u0e34\u0e25\u0e34\u0e40\u0e2d\u0e15"
    ): "affiliate_video_attributed_gmv",
    (
        "GMV \u0e08\u0e32\u0e01\u0e27"
        "\u0e34\u0e14\u0e35\u0e42\u0e2d\u0e02\u0e2d\u0e07"
        "\u0e04\u0e23\u0e35\u0e40\u0e2d\u0e40\u0e15\u0e2d"
        "\u0e23\u0e4c"
    ): "creator_video_direct_gmv",
    (
        "GMV \u0e42\u0e14\u0e22\u0e2d"
        "\u0e49\u0e2d\u0e21\u0e08\u0e32\u0e01\u0e27\u0e34"
        "\u0e14\u0e35\u0e42\u0e2d\u0e02\u0e2d\u0e07\u0e04"
        "\u0e23\u0e35\u0e40\u0e2d\u0e40\u0e15\u0e2d\u0e23"
        "\u0e4c"
    ): "creator_video_indirect_gmv",
    (
        "GMV \u0e08\u0e32\u0e01\u0e27"
        "\u0e34\u0e14\u0e35\u0e42\u0e2d\u0e02\u0e2d\u0e07"
        "\u0e1a\u0e31\u0e0d\u0e0a\u0e35\u0e17\u0e35\u0e48"
        "\u0e40\u0e0a\u0e37\u0e48\u0e2d\u0e21\u0e42\u0e22"
        "\u0e07"
    ): "linked_account_video_gmv",
    (
        "GMV \u0e08\u0e32\u0e01\u0e27"
        "\u0e34\u0e14\u0e35\u0e42\u0e2d\u0e02\u0e2d\u0e07"
        "\u0e1c\u0e39\u0e49\u0e02\u0e32\u0e22"
    ): "seller_video_direct_gmv",
    (
        "GMV \u0e42\u0e14\u0e22\u0e2d"
        "\u0e49\u0e2d\u0e21\u0e08\u0e32\u0e01\u0e27\u0e34"
        "\u0e14\u0e35\u0e42\u0e2d\u0e02\u0e2d\u0e07\u0e1c"
        "\u0e39\u0e49\u0e02\u0e32\u0e22"
    ): "seller_video_indirect_gmv",
}


@dataclass(frozen=True)
class LoadContract:
    source_name: str
    column_mapping: Mapping[str, str]


LOAD_CONTRACTS: dict[str, LoadContract] = {
    "orders": LoadContract(
        source_name="orders",
        column_mapping=_ORDERS_COLUMN_MAPPING,
    ),
    "live_performance": LoadContract(
        source_name="live_performance",
        column_mapping=_LIVE_PERFORMANCE_COLUMN_MAPPING,
    ),
    "shop_analytics": LoadContract(
        source_name="shop_analytics",
        column_mapping=_SHOP_ANALYTICS_COLUMN_MAPPING,
    ),
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
