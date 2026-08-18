from unittest.mock import MagicMock

import pytest

from ecommerce_pipeline.ingestion.audit_lifecycle import (
    FileAuditState,
    mark_file_failed,
    mark_file_processing,
    mark_file_success,
)


def _connection_with_row(row):
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = row

    connection = MagicMock()
    connection.cursor.return_value = cursor

    return connection, cursor


def test_mark_file_processing_sets_processing_state() -> None:
    connection, cursor = _connection_with_row(
        (21, "processing", 10, 0, 0, None)
    )

    result = mark_file_processing(
        connection,
        ingestion_file_id=21,
        rows_discovered=10,
    )

    assert result == FileAuditState(
        ingestion_file_id=21,
        status="processing",
        rows_discovered=10,
        rows_loaded=0,
        rows_rejected=0,
        error_message=None,
    )
    cursor.execute.assert_called_once()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_mark_file_success_records_counts() -> None:
    connection, _ = _connection_with_row(
        (21, "success", 10, 9, 1, None)
    )

    result = mark_file_success(
        connection,
        ingestion_file_id=21,
        rows_discovered=10,
        rows_loaded=9,
        rows_rejected=1,
    )

    assert result.status == "success"
    assert result.rows_discovered == 10
    assert result.rows_loaded == 9
    assert result.rows_rejected == 1
    assert result.error_message is None
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_mark_file_failed_records_error_and_counts() -> None:
    connection, _ = _connection_with_row(
        (21, "failed", 10, 4, 6, "simulated load failure")
    )

    result = mark_file_failed(
        connection,
        ingestion_file_id=21,
        rows_discovered=10,
        rows_loaded=4,
        rows_rejected=6,
        error_message="simulated load failure",
    )

    assert result.status == "failed"
    assert result.rows_loaded == 4
    assert result.rows_rejected == 6
    assert result.error_message == "simulated load failure"
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


@pytest.mark.parametrize(
    ("function_name", "kwargs"),
    [
        ("processing", {"rows_discovered": -1}),
        (
            "success",
            {
                "rows_discovered": -1,
                "rows_loaded": 0,
                "rows_rejected": 0,
            },
        ),
        (
            "failed",
            {
                "rows_discovered": 0,
                "rows_loaded": -1,
                "rows_rejected": 0,
                "error_message": "failure",
            },
        ),
    ],
)
def test_file_lifecycle_rejects_negative_counts(
    function_name: str,
    kwargs: dict[str, object],
) -> None:
    connection = MagicMock()

    if function_name == "processing":
        function = mark_file_processing
    elif function_name == "success":
        function = mark_file_success
    else:
        function = mark_file_failed

    with pytest.raises(ValueError):
        function(connection, ingestion_file_id=21, **kwargs)

    connection.cursor.assert_not_called()


def test_mark_file_failed_rejects_blank_error_message() -> None:
    connection = MagicMock()

    with pytest.raises(
        ValueError,
        match="error_message must not be blank",
    ):
        mark_file_failed(
            connection,
            ingestion_file_id=21,
            rows_discovered=10,
            rows_loaded=0,
            rows_rejected=10,
            error_message="   ",
        )

    connection.cursor.assert_not_called()


@pytest.mark.parametrize(
    "function_name",
    ["processing", "success", "failed"],
)
def test_file_lifecycle_rejects_unknown_file_id(
    function_name: str,
) -> None:
    connection, _ = _connection_with_row(None)

    if function_name == "processing":
        function = mark_file_processing
        kwargs = {"rows_discovered": 10}
    elif function_name == "success":
        function = mark_file_success
        kwargs = {
            "rows_discovered": 10,
            "rows_loaded": 10,
            "rows_rejected": 0,
        }
    else:
        function = mark_file_failed
        kwargs = {
            "rows_discovered": 10,
            "rows_loaded": 0,
            "rows_rejected": 10,
            "error_message": "failure",
        }

    with pytest.raises(
        KeyError,
        match="Unknown ingestion_file_id: 21",
    ):
        function(connection, ingestion_file_id=21, **kwargs)
