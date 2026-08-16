import os
from pathlib import Path

import pytest

from ecommerce_pipeline.ingestion.file_registry import (
    build_file_metadata,
    connect_postgres,
    find_registered_file,
    register_file,
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

    connection.autocommit = False

    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def create_test_ingestion_run(connection) -> int:
    query = """
        INSERT INTO audit.ingestion_runs (
            pipeline_name,
            run_type,
            status
        )
        VALUES (
            'pytest_file_registry',
            'manual',
            'running'
        )
        RETURNING ingestion_run_id;
    """

    with connection.cursor() as cursor:
        cursor.execute(query)
        row = cursor.fetchone()

    return row[0]


def test_register_new_file_in_postgres(
    postgres_connection,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "orders_integration.csv"
    file_path.write_text(
        "order_id,sku_id\nORDER_INT_001,SKU_INT_001\n",
        encoding="utf-8",
    )

    metadata = build_file_metadata(
        source_name="orders",
        file_path=file_path,
    )

    ingestion_run_id = create_test_ingestion_run(
        postgres_connection
    )

    result = register_file(
        connection=postgres_connection,
        ingestion_run_id=ingestion_run_id,
        metadata=metadata,
    )

    assert result.ingestion_file_id > 0
    assert result.source_name == "orders"
    assert result.file_hash_sha256 == metadata.file_hash_sha256
    assert result.status == "discovered"
    assert result.is_duplicate is False


def test_find_registered_file_returns_existing_file(
    postgres_connection,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "orders_find_existing.csv"
    file_path.write_text(
        "order_id,sku_id\nORDER_INT_002,SKU_INT_002\n",
        encoding="utf-8",
    )

    metadata = build_file_metadata(
        source_name="orders",
        file_path=file_path,
    )

    ingestion_run_id = create_test_ingestion_run(
        postgres_connection
    )

    registered = register_file(
        connection=postgres_connection,
        ingestion_run_id=ingestion_run_id,
        metadata=metadata,
    )

    found = find_registered_file(
        connection=postgres_connection,
        source_name="orders",
        file_hash_sha256=metadata.file_hash_sha256,
    )

    assert found is not None
    assert found.ingestion_file_id == registered.ingestion_file_id
    assert found.source_name == "orders"
    assert found.file_hash_sha256 == metadata.file_hash_sha256
    assert found.status == "discovered"
    assert found.is_duplicate is True


def test_register_same_file_twice_detects_duplicate(
    postgres_connection,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "orders_duplicate.csv"
    file_path.write_text(
        "order_id,sku_id\nORDER_INT_003,SKU_INT_003\n",
        encoding="utf-8",
    )

    metadata = build_file_metadata(
        source_name="orders",
        file_path=file_path,
    )

    ingestion_run_id = create_test_ingestion_run(
        postgres_connection
    )

    first_result = register_file(
        connection=postgres_connection,
        ingestion_run_id=ingestion_run_id,
        metadata=metadata,
    )

    second_result = register_file(
        connection=postgres_connection,
        ingestion_run_id=ingestion_run_id,
        metadata=metadata,
    )

    assert first_result.is_duplicate is False
    assert second_result.is_duplicate is True

    assert (
        second_result.ingestion_file_id
        == first_result.ingestion_file_id
    )

    assert (
        second_result.file_hash_sha256
        == first_result.file_hash_sha256
    )


def test_same_file_content_can_exist_for_different_sources(
    postgres_connection,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "shared_content.xlsx"
    file_path.write_bytes(b"same-file-content-across-sources")

    orders_metadata = build_file_metadata(
        source_name="orders",
        file_path=file_path,
    )

    shop_metadata = build_file_metadata(
        source_name="shop_analytics",
        file_path=file_path,
    )

    ingestion_run_id = create_test_ingestion_run(
        postgres_connection
    )

    orders_result = register_file(
        connection=postgres_connection,
        ingestion_run_id=ingestion_run_id,
        metadata=orders_metadata,
    )

    shop_result = register_file(
        connection=postgres_connection,
        ingestion_run_id=ingestion_run_id,
        metadata=shop_metadata,
    )

    assert orders_result.file_hash_sha256 == shop_result.file_hash_sha256
    assert orders_result.ingestion_file_id != shop_result.ingestion_file_id

    assert orders_result.is_duplicate is False
    assert shop_result.is_duplicate is False