import os

import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.ingestion.pii_boundary import (
    list_pii_columns,
    validate_projection_boundary,
)


@pytest.fixture
def postgres_connection():
    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )

    try:
        yield connection
    finally:
        connection.close()


def test_orders_pii_policy_matches_live_raw_schema(
    postgres_connection,
) -> None:
    classified_pii_columns = set(list_pii_columns("orders"))

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'raw'
              AND table_name = 'orders';
            """
        )
        live_columns = {
            row[0]
            for row in cursor.fetchall()
        }

    assert classified_pii_columns
    assert classified_pii_columns <= live_columns

    public_result = validate_projection_boundary(
        source_name="orders",
        requested_columns=(
            "order_id",
            "buyer_username",
            "phone_number",
            "tax_info_email",
        ),
        boundary="public",
    )

    assert public_result.is_allowed is False
    assert public_result.blocked_columns == (
        "buyer_username",
        "phone_number",
        "tax_info_email",
    )
