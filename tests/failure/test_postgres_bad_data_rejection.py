"""Failure-injection drill: bad data rejection at the raw.orders boundary.

Safety boundary:
- The drill inserts one synthetic row into raw.orders inside a transaction that
  is always rolled back; no business row is ever persisted or modified.
- The row violates chk_raw_orders_order_id_not_blank (whitespace order_id).
  CHECK constraints are evaluated before foreign-key triggers, so the insert is
  deterministically rejected regardless of audit control-plane contents.
- All connections are closed in ``finally`` even when an assertion fails.
"""

import os

import psycopg2
import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres


def _connect():
    return connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )


def _row_count(cursor) -> int:
    cursor.execute("SELECT COUNT(*) FROM raw.orders;")
    return int(cursor.fetchone()[0])


def test_blank_order_id_is_rejected_and_no_row_leaks() -> None:
    connection = _connect()
    try:
        with connection.cursor() as cursor:
            before_count = _row_count(cursor)

            # INJECT: attempt to load a row whose order_id is whitespace-only.
            # All other NOT NULL columns get plausible synthetic values.
            with pytest.raises(psycopg2.IntegrityError) as exc_info:
                cursor.execute(
                    """
                    INSERT INTO raw.orders (
                        order_id,
                        sku_id,
                        _source_file,
                        _source_row_number,
                        _batch_id,
                        _file_hash,
                        _pipeline_run_id,
                        _ingestion_file_id
                    ) VALUES (
                        '   ',
                        'drill-sku',
                        'drill_source.csv',
                        1,
                        'drill-batch',
                        %s,
                        0,
                        0
                    );
                    """,
                    ("0" * 64,),
                )
            # DETECT: the not-blank CHECK must be what rejected the row.
            assert isinstance(exc_info.value, psycopg2.errors.CheckViolation), (
                f"expected CheckViolation, got {type(exc_info.value).__name__}: "
                f"{exc_info.value}"
            )

            # RECOVER: roll back the drill transaction.
            connection.rollback()

            # VERIFY: the rejected row never leaked into raw.orders.
            after_count = _row_count(cursor)
            assert after_count == before_count
    finally:
        connection.rollback()
        connection.close()
