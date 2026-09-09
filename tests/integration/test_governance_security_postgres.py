import os

import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres


@pytest.fixture
def admin_connection():
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
def test_capability_roles_are_non_login_and_non_superuser(admin_connection) -> None:
    with admin_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolcanlogin
            FROM pg_roles
            WHERE rolname IN (
                'ecommerce_ingest_writer',
                'ecommerce_transformer',
                'ecommerce_analytics_reader'
            )
            ORDER BY rolname
            """
        )
        rows = cursor.fetchall()

    assert len(rows) == 3
    assert all(row[1:] == (False, False, False, False) for row in rows)


def test_transformer_has_only_required_database_and_orders_access(admin_connection) -> None:
    with admin_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              has_database_privilege('ecommerce_transformer', 'ecommerce', 'TEMP'),
              has_column_privilege('ecommerce_transformer', 'raw.orders', 'order_id', 'SELECT'),
              has_column_privilege(
                'ecommerce_transformer', 'raw.orders', 'buyer_username', 'SELECT'
              ),
              has_column_privilege('ecommerce_transformer', 'raw.orders', 'tracking_id', 'SELECT')
            """
        )
        row = cursor.fetchone()

    assert row == (True, True, False, False)
def test_analytics_reader_is_marts_only(admin_connection) -> None:
    with admin_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
              has_table_privilege(
                'ecommerce_analytics_reader',
                'analytics_marts.fact_orders',
                'SELECT'
              ),
              has_table_privilege(
                'ecommerce_analytics_reader',
                'raw.orders',
                'SELECT'
              ),
              has_table_privilege(
                'ecommerce_analytics_reader',
                'audit.ingestion_runs',
                'SELECT'
              )
            """
        )
        row = cursor.fetchone()

    assert row == (True, False, False)


def test_retention_registry_is_non_destructive_by_default(admin_connection) -> None:
    with admin_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT policy_key, policy_status, retention_days, enforcement_enabled
            FROM audit.data_retention_policies
            ORDER BY policy_key
            """
        )
        rows = cursor.fetchall()

    assert len(rows) == 4
    assert all(row[1] == "pending_business_approval" for row in rows)
    assert all(row[2] is None for row in rows)
    assert all(row[3] is False for row in rows)
