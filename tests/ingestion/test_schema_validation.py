
import pytest

from ecommerce_pipeline.ingestion.schema_contracts import get_schema_contract
from ecommerce_pipeline.ingestion.schema_validation import (
    find_duplicate_columns,
    find_missing_required_columns,
    normalize_column_name,
    normalize_columns,
    validate_schema,
)


def _make_columns(
    total: int,
    required: tuple[str, ...] = (),
) -> list[str]:
    columns = list(required)

    while len(columns) < total:
        columns.append(f"column_{len(columns) + 1}")

    return columns


def test_normalize_column_name_trims_and_casefolds() -> None:
    assert normalize_column_name("  Order ID  ") == "order id"


def test_normalize_column_name_can_preserve_case() -> None:
    assert (
        normalize_column_name(
            "  Order ID  ",
            trim=True,
            case_sensitive=True,
        )
        == "Order ID"
    )


def test_normalize_column_name_can_preserve_whitespace() -> None:
    assert (
        normalize_column_name(
            "  Order ID  ",
            trim=False,
            case_sensitive=False,
        )
        == "  order id  "
    )


def test_normalize_columns_uses_contract_rules() -> None:
    contract = get_schema_contract("orders")

    normalized = normalize_columns(
        [" Order ID ", "SKU ID"],
        contract,
    )

    assert normalized == ("order id", "sku id")


def test_find_duplicate_columns_returns_sorted_unique_duplicates() -> None:
    duplicates = find_duplicate_columns(
        [
            "order id",
            "sku id",
            "order id",
            "sku id",
            "order id",
        ]
    )

    assert duplicates == ("order id", "sku id")


def test_find_duplicate_columns_returns_empty_tuple() -> None:
    assert find_duplicate_columns(["a", "b", "c"]) == ()


def test_find_missing_required_columns_returns_empty_when_present() -> None:
    contract = get_schema_contract("orders")

    missing = find_missing_required_columns(
        normalized_columns=("order id", "sku id"),
        contract=contract,
    )

    assert missing == ()


def test_find_missing_required_columns_detects_missing_order_id() -> None:
    contract = get_schema_contract("orders")

    missing = find_missing_required_columns(
        normalized_columns=("sku id",),
        contract=contract,
    )

    assert missing == ("order_id",)


def test_validate_orders_schema_is_valid_when_contract_matches() -> None:
    columns = _make_columns(
        65,
        required=("Order ID", "SKU ID"),
    )

    result = validate_schema(
        source_name="orders",
        observed_columns=columns,
    )

    assert result.status == "VALID"
    assert result.source_name == "orders"
    assert result.observed_column_count == 65
    assert result.expected_column_count == 65
    assert result.missing_required_columns == ()
    assert result.duplicate_columns == ()
    assert result.issues == ()


def test_validate_schema_accepts_required_column_aliases() -> None:
    columns = _make_columns(
        65,
        required=("order_id", "sku_id"),
    )

    result = validate_schema(
        source_name="orders",
        observed_columns=columns,
    )

    assert result.status == "VALID"


def test_validate_schema_accepts_required_columns_case_insensitively() -> None:
    columns = _make_columns(
        65,
        required=("ORDER ID", "SKU ID"),
    )

    result = validate_schema(
        source_name="orders",
        observed_columns=columns,
    )

    assert result.status == "VALID"


def test_validate_schema_accepts_required_columns_with_whitespace() -> None:
    columns = _make_columns(
        65,
        required=("  Order ID  ", "  SKU ID  "),
    )

    result = validate_schema(
        source_name="orders",
        observed_columns=columns,
    )

    assert result.status == "VALID"


def test_validate_schema_is_invalid_on_column_count_mismatch() -> None:
    columns = _make_columns(
        64,
        required=("Order ID", "SKU ID"),
    )

    result = validate_schema(
        source_name="orders",
        observed_columns=columns,
    )

    assert result.status == "INVALID"
    assert result.observed_column_count == 64
    assert result.expected_column_count == 65

    issue_codes = {issue.code for issue in result.issues}

    assert "COLUMN_COUNT_MISMATCH" in issue_codes


def test_validate_schema_is_invalid_on_missing_required_column() -> None:
    columns = _make_columns(
        65,
        required=("Order ID",),
    )

    result = validate_schema(
        source_name="orders",
        observed_columns=columns,
    )

    assert result.status == "INVALID"
    assert result.missing_required_columns == ("sku_id",)

    missing_issues = [
        issue
        for issue in result.issues
        if issue.code == "MISSING_REQUIRED_COLUMN"
    ]

    assert len(missing_issues) == 1
    assert missing_issues[0].column_name == "sku_id"
    assert missing_issues[0].severity == "ERROR"


def test_validate_schema_is_invalid_on_duplicate_columns() -> None:
    columns = _make_columns(
        65,
        required=("Order ID", "SKU ID"),
    )
    columns[-1] = "Order ID"

    result = validate_schema(
        source_name="orders",
        observed_columns=columns,
    )

    assert result.status == "INVALID"
    assert result.duplicate_columns == ("order id",)

    duplicate_issues = [
        issue
        for issue in result.issues
        if issue.code == "DUPLICATE_COLUMN"
    ]

    assert len(duplicate_issues) == 1
    assert duplicate_issues[0].column_name == "order id"
    assert duplicate_issues[0].severity == "ERROR"


def test_duplicate_detection_occurs_after_normalization() -> None:
    columns = _make_columns(
        65,
        required=("Order ID", "SKU ID"),
    )
    columns[-1] = " order id "

    result = validate_schema(
        source_name="orders",
        observed_columns=columns,
    )

    assert result.status == "INVALID"
    assert result.duplicate_columns == ("order id",)


def test_validate_schema_can_report_multiple_errors() -> None:
    columns = _make_columns(
        64,
        required=("Order ID",),
    )
    columns[-1] = "Order ID"

    result = validate_schema(
        source_name="orders",
        observed_columns=columns,
    )

    issue_codes = {issue.code for issue in result.issues}

    assert result.status == "INVALID"
    assert "COLUMN_COUNT_MISMATCH" in issue_codes
    assert "DUPLICATE_COLUMN" in issue_codes
    assert "MISSING_REQUIRED_COLUMN" in issue_codes


def test_campaign_schema_can_validate_without_invented_required_columns() -> None:
    columns = _make_columns(7)

    result = validate_schema(
        source_name="campaign_overview",
        observed_columns=columns,
    )

    assert result.status == "VALID"
    assert result.missing_required_columns == ()


def test_shop_analytics_requires_metric_date() -> None:
    columns = _make_columns(28)

    result = validate_schema(
        source_name="shop_analytics",
        observed_columns=columns,
    )

    assert result.status == "INVALID"
    assert result.missing_required_columns == ("metric_date",)


def test_shop_analytics_accepts_date_alias() -> None:
    columns = _make_columns(
        28,
        required=("Date",),
    )

    result = validate_schema(
        source_name="shop_analytics",
        observed_columns=columns,
    )

    assert result.status == "VALID"


def test_live_performance_accepts_metric_date_alias() -> None:
    columns = _make_columns(
        18,
        required=("metric_date",),
    )

    result = validate_schema(
        source_name="live_performance",
        observed_columns=columns,
    )

    assert result.status == "VALID"


def test_product_card_traffic_accepts_date_alias() -> None:
    columns = _make_columns(
        16,
        required=("Date",),
    )

    result = validate_schema(
        source_name="product_card_traffic",
        observed_columns=columns,
    )

    assert result.status == "VALID"


def test_product_master_accepts_product_id_alias() -> None:
    columns = _make_columns(
        176,
        required=("Product ID",),
    )

    result = validate_schema(
        source_name="product_master",
        observed_columns=columns,
    )

    assert result.status == "VALID"


def test_sku_master_requires_sku_id_and_product_id() -> None:
    columns = _make_columns(
        7,
        required=("SKU ID",),
    )

    result = validate_schema(
        source_name="sku_master",
        observed_columns=columns,
    )

    assert result.status == "INVALID"
    assert result.missing_required_columns == ("product_id",)


def test_sku_master_valid_when_required_columns_present() -> None:
    columns = _make_columns(
        7,
        required=("SKU ID", "Product ID"),
    )

    result = validate_schema(
        source_name="sku_master",
        observed_columns=columns,
    )

    assert result.status == "VALID"


def test_validate_schema_rejects_unknown_source() -> None:
    with pytest.raises(
        KeyError,
        match="Unknown schema contract 'does_not_exist'",
    ):
        validate_schema(
            source_name="does_not_exist",
            observed_columns=[],
        )


def test_result_preserves_normalized_columns() -> None:
    columns = _make_columns(
        65,
        required=(" Order ID ", " SKU ID "),
    )

    result = validate_schema(
        source_name="orders",
        observed_columns=columns,
    )

    assert result.normalized_columns[0] == "order id"
    assert result.normalized_columns[1] == "sku id"
