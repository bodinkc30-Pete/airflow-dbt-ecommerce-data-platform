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


def test_shop_analytics_load_contract_contains_verified_twenty_eight_columns() -> None:
    contract = get_load_contract("shop_analytics")

    assert contract.source_name == "shop_analytics"
    assert len(contract.column_mapping) == 28
    assert tuple(contract.column_mapping.values()) == (
        "metric_date",
        "gmv",
        "orders",
        "customers",
        "items_sold",
        "refunds",
        "sku_orders",
        "gross_revenue",
        "page_views",
        "visitors",
        "conversion_rate",
        "product_impressions",
        "unique_product_impressions",
        "product_clicks",
        "unique_product_clicks",
        "aov",
        "creator_live_attributed_gmv",
        "creator_live_direct_gmv",
        "creator_live_indirect_gmv",
        "linked_account_live_gmv",
        "seller_live_direct_gmv",
        "seller_live_indirect_gmv",
        "affiliate_video_attributed_gmv",
        "creator_video_direct_gmv",
        "creator_video_indirect_gmv",
        "linked_account_video_gmv",
        "seller_video_direct_gmv",
        "seller_video_indirect_gmv",
    )


def test_orders_load_contract_contains_verified_sixty_five_columns() -> None:
    contract = get_load_contract("orders")

    expected_source_columns = (
        "Order ID",
        "Order Status",
        "Order Substatus",
        "Cancelation/Return Type",
        "Normal or Pre-order",
        "SKU ID",
        "Seller SKU",
        "Product Name",
        "Variation",
        "Quantity",
        "Sku Quantity of return",
        "SKU Unit Original Price",
        "SKU Subtotal Before Discount",
        "SKU Platform Discount",
        "SKU Seller Discount",
        "SKU Subtotal After Discount",
        "Shipping Fee After Discount",
        "Original Shipping Fee",
        "Shipping Fee Seller Discount",
        "Shipping Fee Platform Discount",
        "Payment platform discount",
        "Taxes",
        "Order Amount",
        "Order Refund Amount",
        "Created Time",
        "Paid Time",
        "RTS Time",
        "Shipped Time",
        "Delivered Time",
        "Cancelled Time",
        "Cancel By",
        "Cancel Reason",
        "Fulfillment Type",
        "Warehouse Name",
        "Tracking ID",
        "Delivery Option",
        "Shipping Provider Name",
        "Buyer Message",
        "Buyer Username",
        "Recipient",
        "Phone #",
        "Zipcode",
        "Country",
        "Province",
        "District",
        "Districts",
        "Detail Address",
        "Additional address information",
        "Payment Method",
        "Weight(kg)",
        "Product Category",
        "Package ID",
        "Seller Note",
        "Checked Status",
        "Checked Marked by",
        "Order Channel",
        "Creator Handle",
        "Request Tax Invoice",
        "Tax Info - Buyer Tax ID",
        "Tax Info - Type",
        "Tax Info - Full Name of Buyer",
        "Tax Info - Email",
        "Tax Info - Phone Number",
        "Tax Info - Registered Address",
        "Tax Info - Address Type",
    )
    expected_destination_columns = (
        "order_id",
        "order_status",
        "order_substatus",
        "cancelation_return_type",
        "normal_or_pre_order",
        "sku_id",
        "seller_sku",
        "product_name",
        "variation",
        "quantity",
        "sku_quantity_of_return",
        "sku_unit_original_price",
        "sku_subtotal_before_discount",
        "sku_platform_discount",
        "sku_seller_discount",
        "sku_subtotal_after_discount",
        "shipping_fee_after_discount",
        "original_shipping_fee",
        "shipping_fee_seller_discount",
        "shipping_fee_platform_discount",
        "payment_platform_discount",
        "taxes",
        "order_amount",
        "order_refund_amount",
        "created_time",
        "paid_time",
        "rts_time",
        "shipped_time",
        "delivered_time",
        "cancelled_time",
        "cancel_by",
        "cancel_reason",
        "fulfillment_type",
        "warehouse_name",
        "tracking_id",
        "delivery_option",
        "shipping_provider_name",
        "buyer_message",
        "buyer_username",
        "recipient",
        "phone_number",
        "zipcode",
        "country",
        "province",
        "district",
        "districts",
        "detail_address",
        "additional_address_information",
        "payment_method",
        "weight_kg",
        "product_category",
        "package_id",
        "seller_note",
        "checked_status",
        "checked_marked_by",
        "order_channel",
        "creator_handle",
        "request_tax_invoice",
        "tax_info_buyer_tax_id",
        "tax_info_type",
        "tax_info_full_name_of_buyer",
        "tax_info_email",
        "tax_info_phone_number",
        "tax_info_registered_address",
        "tax_info_address_type",
    )

    assert contract.source_name == "orders"
    assert tuple(contract.column_mapping) == expected_source_columns
    assert tuple(contract.column_mapping.values()) == expected_destination_columns



def test_only_verified_load_contracts_are_registered() -> None:
    assert set(LOAD_CONTRACTS) == {"campaign_overview", "orders", "shop_analytics"}
    assert list_load_contract_names() == (
        "campaign_overview",
        "orders",
        "shop_analytics",
    )


def test_validate_load_contracts_passes() -> None:
    validate_load_contracts()
