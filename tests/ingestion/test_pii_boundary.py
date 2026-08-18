import pytest

from ecommerce_pipeline.ingestion.pii_boundary import (
    list_pii_columns,
    require_safe_projection,
    validate_projection_boundary,
)


def test_orders_pii_columns_include_contract_backed_fields() -> None:
    pii_columns = set(list_pii_columns("orders"))

    assert {
        "buyer_username",
        "recipient",
        "phone_number",
        "detail_address",
        "tax_info_buyer_tax_id",
        "tax_info_email",
        "tax_info_registered_address",
    } <= pii_columns


def test_private_raw_boundary_allows_pii_columns() -> None:
    result = validate_projection_boundary(
        source_name="orders",
        requested_columns=(
            "order_id",
            "buyer_username",
            "phone_number",
        ),
        boundary="private_raw",
    )

    assert result.is_allowed is True
    assert result.blocked_columns == ()


def test_downstream_safe_boundary_blocks_pii_columns() -> None:
    result = validate_projection_boundary(
        source_name="orders",
        requested_columns=(
            "order_id",
            "sku_id",
            "buyer_username",
            "phone_number",
        ),
        boundary="downstream_safe",
    )

    assert result.is_allowed is False
    assert result.blocked_columns == (
        "buyer_username",
        "phone_number",
    )


def test_public_boundary_allows_non_pii_business_columns() -> None:
    result = validate_projection_boundary(
        source_name="orders",
        requested_columns=(
            "order_id",
            "sku_id",
            "order_status",
            "order_amount",
        ),
        boundary="public",
    )

    assert result.is_allowed is True
    assert result.blocked_columns == ()


def test_public_boundary_blocks_free_text_sensitive_columns() -> None:
    result = validate_projection_boundary(
        source_name="orders",
        requested_columns=(
            "order_id",
            "buyer_message",
            "seller_note",
        ),
        boundary="public",
    )

    assert result.is_allowed is False
    assert result.blocked_columns == (
        "buyer_message",
        "seller_note",
    )


def test_require_safe_projection_raises_without_exposing_values() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "PII boundary violation for source 'orders' "
            "at boundary 'public': recipient, tax_info_email"
        ),
    ):
        require_safe_projection(
            source_name="orders",
            requested_columns=(
                "order_id",
                "recipient",
                "tax_info_email",
            ),
            boundary="public",
        )


def test_source_without_classified_pii_allows_projection() -> None:
    result = validate_projection_boundary(
        source_name="shop_analytics",
        requested_columns=(
            "metric_date",
            "gmv",
            "orders",
        ),
        boundary="downstream_safe",
    )

    assert result.is_allowed is True
    assert result.blocked_columns == ()
