from unittest.mock import MagicMock

from ecommerce_pipeline.ingestion.incremental_state import (
    WatermarkState,
    get_watermark_state,
    upsert_watermark_state,
)


def test_get_watermark_state_returns_none_when_missing() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor

    result = get_watermark_state(
        connection,
        source_name="orders",
    )

    assert result is None

    cursor.execute.assert_called_once_with(
        """
        SELECT
            source_name,
            watermark_type,
            watermark_value,
            last_successful_run_id,
            last_successful_file_id
        FROM audit.source_watermarks
        WHERE source_name = %s;
    """,
        ("orders",),
    )


def test_get_watermark_state_returns_existing_state() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = (
        "orders",
        "file",
        "2026-08-17/orders.csv",
        101,
        202,
    )

    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor

    result = get_watermark_state(
        connection,
        source_name="orders",
    )

    assert result == WatermarkState(
        source_name="orders",
        watermark_type="file",
        watermark_value="2026-08-17/orders.csv",
        last_successful_run_id=101,
        last_successful_file_id=202,
    )


def test_upsert_watermark_state_returns_current_state() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = (
        "orders",
        "file",
        "2026-08-18/orders.csv",
        102,
        203,
    )

    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor

    result = upsert_watermark_state(
        connection,
        source_name="orders",
        watermark_type="file",
        watermark_value="2026-08-18/orders.csv",
        last_successful_run_id=102,
        last_successful_file_id=203,
    )

    assert result == WatermarkState(
        source_name="orders",
        watermark_type="file",
        watermark_value="2026-08-18/orders.csv",
        last_successful_run_id=102,
        last_successful_file_id=203,
    )

    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
