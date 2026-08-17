from unittest.mock import MagicMock

from ecommerce_pipeline.ingestion.schema_drift import (
    classify_schema_drift,
    record_schema_events,
)
from ecommerce_pipeline.ingestion.schema_validation import (
    validate_schema,
)


def _make_columns(
    count: int,
    *,
    required: tuple[str, ...] = (),
) -> list[str]:
    columns = [f"column_{index}" for index in range(count)]

    for index, column_name in enumerate(required):
        columns[index] = column_name

    return columns


def test_missing_required_column_maps_to_missing_column_event() -> None:
    result = validate_schema(
        source_name="orders",
        observed_columns=_make_columns(
            65,
            required=("Order ID",),
        ),
    )

    events = classify_schema_drift(result)

    missing_events = [
        event
        for event in events
        if event.event_type == "missing_column"
    ]

    assert len(missing_events) == 1

    event = missing_events[0]

    assert event.source_name == "orders"
    assert event.column_name == "sku_id"
    assert event.expected_value == "required"
    assert event.observed_value == "missing"
    assert event.severity == "error"
    assert (
        event.details["validation_issue_code"]
        == "MISSING_REQUIRED_COLUMN"
    )


def test_column_count_mismatch_maps_to_other_without_inventing_column() -> None:
    result = validate_schema(
        source_name="orders",
        observed_columns=_make_columns(
            64,
            required=("Order ID", "SKU ID"),
        ),
    )

    events = classify_schema_drift(result)

    count_events = [
        event
        for event in events
        if event.details["validation_issue_code"]
        == "COLUMN_COUNT_MISMATCH"
    ]

    assert len(count_events) == 1

    event = count_events[0]

    assert event.event_type == "other"
    assert event.column_name is None
    assert event.expected_value == "65"
    assert event.observed_value == "64"


def test_duplicate_column_maps_to_other_with_column_name() -> None:
    columns = _make_columns(
        65,
        required=("Order ID", "SKU ID"),
    )
    columns[-1] = "Order ID"

    result = validate_schema(
        source_name="orders",
        observed_columns=columns,
    )

    events = classify_schema_drift(result)

    duplicate_events = [
        event
        for event in events
        if event.details["validation_issue_code"]
        == "DUPLICATE_COLUMN"
    ]

    assert len(duplicate_events) == 1

    event = duplicate_events[0]

    assert event.event_type == "other"
    assert event.column_name == "order id"
    assert event.expected_value == "unique_column_name"
    assert event.observed_value == "duplicate"


def test_valid_schema_produces_no_events() -> None:
    result = validate_schema(
        source_name="orders",
        observed_columns=_make_columns(
            65,
            required=("Order ID", "SKU ID"),
        ),
    )

    assert classify_schema_drift(result) == ()


def test_record_schema_events_is_transaction_neutral() -> None:
    result = validate_schema(
        source_name="orders",
        observed_columns=_make_columns(
            65,
            required=("Order ID",),
        ),
    )
    events = classify_schema_drift(result)

    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = (101,)

    connection = MagicMock()
    connection.cursor.return_value = cursor

    event_ids = record_schema_events(
        connection,
        ingestion_run_id=11,
        ingestion_file_id=22,
        events=events,
    )

    assert event_ids
    assert all(event_id == 101 for event_id in event_ids)
    assert cursor.execute.call_count == len(events)
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_record_schema_events_returns_empty_without_db_write() -> None:
    connection = MagicMock()

    event_ids = record_schema_events(
        connection,
        ingestion_run_id=11,
        ingestion_file_id=22,
        events=(),
    )

    assert event_ids == ()
    connection.cursor.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
