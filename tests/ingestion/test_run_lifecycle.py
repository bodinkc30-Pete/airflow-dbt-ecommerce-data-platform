from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from ecommerce_pipeline.ingestion.run_lifecycle import (
    IngestionRunState,
    create_ingestion_run,
    mark_run_failed,
    mark_run_success,
)


def _connection_with_row(row):
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = row

    connection = MagicMock()
    connection.cursor.return_value = cursor

    return connection, cursor


def _connection_with_rows(rows):
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.side_effect = rows

    connection = MagicMock()
    connection.cursor.return_value = cursor

    return connection, cursor


def _run_row(
    *,
    status: str = "running",
    finished_at=None,
    files_discovered: int = 0,
    files_processed: int = 0,
    files_failed: int = 0,
    rows_discovered: int = 0,
    rows_loaded: int = 0,
    rows_rejected: int = 0,
    error_message=None,
):
    started_at = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)

    return (
        31,
        "ecommerce_ingestion",
        "manual",
        started_at,
        finished_at,
        status,
        files_discovered,
        files_processed,
        files_failed,
        rows_discovered,
        rows_loaded,
        rows_rejected,
        error_message,
    )


def test_create_ingestion_run_returns_running_state() -> None:
    connection, cursor = _connection_with_row(_run_row())

    result = create_ingestion_run(
        connection,
        pipeline_name="ecommerce_ingestion",
        run_type="manual",
    )

    assert result == IngestionRunState(
        ingestion_run_id=31,
        pipeline_name="ecommerce_ingestion",
        run_type="manual",
        started_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
        finished_at=None,
        status="running",
        files_discovered=0,
        files_processed=0,
        files_failed=0,
        rows_discovered=0,
        rows_loaded=0,
        rows_rejected=0,
        error_message=None,
    )
    cursor.execute.assert_called_once()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_create_ingestion_run_rejects_blank_pipeline_name() -> None:
    connection = MagicMock()

    with pytest.raises(
        ValueError,
        match="pipeline_name must not be blank",
    ):
        create_ingestion_run(
            connection,
            pipeline_name="   ",
            run_type="manual",
        )

    connection.cursor.assert_not_called()


def test_create_ingestion_run_rejects_unknown_run_type() -> None:
    connection = MagicMock()

    with pytest.raises(ValueError, match="run_type must be one of:"):
        create_ingestion_run(
            connection,
            pipeline_name="ecommerce_ingestion",
            run_type="unknown",
        )

    connection.cursor.assert_not_called()


def test_mark_run_success_records_terminal_state() -> None:
    finished_at = datetime(2026, 8, 21, 12, 5, tzinfo=UTC)
    connection, _ = _connection_with_row(
        _run_row(
            status="success",
            finished_at=finished_at,
            files_discovered=2,
            files_processed=2,
            files_failed=0,
            rows_discovered=20,
            rows_loaded=19,
            rows_rejected=1,
        )
    )

    result = mark_run_success(
        connection,
        ingestion_run_id=31,
        files_discovered=2,
        files_processed=2,
        files_failed=0,
        rows_discovered=20,
        rows_loaded=19,
        rows_rejected=1,
    )

    assert result.status == "success"
    assert result.finished_at == finished_at
    assert result.files_processed == 2
    assert result.rows_loaded == 19
    assert result.error_message is None
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_mark_run_failed_records_error_and_counts() -> None:
    finished_at = datetime(2026, 8, 21, 12, 5, tzinfo=UTC)
    connection, _ = _connection_with_row(
        _run_row(
            status="failed",
            finished_at=finished_at,
            files_discovered=2,
            files_processed=1,
            files_failed=1,
            rows_discovered=20,
            rows_loaded=10,
            rows_rejected=10,
            error_message="simulated run failure",
        )
    )

    result = mark_run_failed(
        connection,
        ingestion_run_id=31,
        files_discovered=2,
        files_processed=1,
        files_failed=1,
        rows_discovered=20,
        rows_loaded=10,
        rows_rejected=10,
        error_message="simulated run failure",
    )

    assert result.status == "failed"
    assert result.files_failed == 1
    assert result.rows_rejected == 10
    assert result.error_message == "simulated run failure"
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


@pytest.mark.parametrize(
    ("function_name", "kwargs"),
    [
        (
            "success",
            {
                "files_discovered": -1,
                "files_processed": 0,
                "files_failed": 0,
                "rows_discovered": 0,
                "rows_loaded": 0,
                "rows_rejected": 0,
            },
        ),
        (
            "failed",
            {
                "files_discovered": 1,
                "files_processed": 0,
                "files_failed": 1,
                "rows_discovered": 1,
                "rows_loaded": -1,
                "rows_rejected": 1,
                "error_message": "failure",
            },
        ),
    ],
)
def test_run_lifecycle_rejects_negative_counts(
    function_name: str,
    kwargs: dict[str, object],
) -> None:
    connection = MagicMock()

    function = mark_run_success if function_name == "success" else mark_run_failed

    with pytest.raises(ValueError):
        function(connection, ingestion_run_id=31, **kwargs)

    connection.cursor.assert_not_called()


def test_mark_run_failed_rejects_blank_error_message() -> None:
    connection = MagicMock()

    with pytest.raises(
        ValueError,
        match="error_message must not be blank",
    ):
        mark_run_failed(
            connection,
            ingestion_run_id=31,
            files_discovered=1,
            files_processed=0,
            files_failed=1,
            rows_discovered=0,
            rows_loaded=0,
            rows_rejected=0,
            error_message="   ",
        )

    connection.cursor.assert_not_called()


@pytest.mark.parametrize(
    ("function_name", "current_status"),
    [
        ("success", "failed"),
        ("failed", "success"),
    ],
)
def test_run_lifecycle_rejects_terminal_state_transition(
    function_name: str,
    current_status: str,
) -> None:
    connection, cursor = _connection_with_rows([None, (current_status,)])

    if function_name == "success":
        function = mark_run_success
        kwargs = {
            "files_discovered": 1,
            "files_processed": 1,
            "files_failed": 0,
            "rows_discovered": 10,
            "rows_loaded": 10,
            "rows_rejected": 0,
        }
    else:
        function = mark_run_failed
        kwargs = {
            "files_discovered": 1,
            "files_processed": 0,
            "files_failed": 1,
            "rows_discovered": 10,
            "rows_loaded": 0,
            "rows_rejected": 10,
            "error_message": "failure",
        }

    with pytest.raises(
        RuntimeError,
        match=(
            rf"Ingestion run 31 must be running to change terminal state; "
            rf"current status: {current_status}"
        ),
    ):
        function(connection, ingestion_run_id=31, **kwargs)

    assert cursor.execute.call_count == 2
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


@pytest.mark.parametrize(
    "function_name",
    ["success", "failed"],
)
def test_run_lifecycle_rejects_unknown_run_id(
    function_name: str,
) -> None:
    connection, _ = _connection_with_row(None)

    if function_name == "success":
        function = mark_run_success
        kwargs = {
            "files_discovered": 1,
            "files_processed": 1,
            "files_failed": 0,
            "rows_discovered": 10,
            "rows_loaded": 10,
            "rows_rejected": 0,
        }
    else:
        function = mark_run_failed
        kwargs = {
            "files_discovered": 1,
            "files_processed": 0,
            "files_failed": 1,
            "rows_discovered": 10,
            "rows_loaded": 0,
            "rows_rejected": 10,
            "error_message": "failure",
        }

    with pytest.raises(
        KeyError,
        match="Unknown ingestion_run_id: 31",
    ):
        function(connection, ingestion_run_id=31, **kwargs)
