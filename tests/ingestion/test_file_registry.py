from hashlib import sha256
from pathlib import Path

import pytest

from ecommerce_pipeline.ingestion.file_registry import (
    build_file_metadata,
    calculate_sha256,
)


def test_calculate_sha256_matches_expected_hash(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    content = b"project-06-file-registry"

    file_path.write_bytes(content)

    expected_hash = sha256(content).hexdigest()

    assert calculate_sha256(file_path) == expected_hash


def test_calculate_sha256_is_deterministic(tmp_path: Path) -> None:
    file_path = tmp_path / "deterministic.txt"
    file_path.write_text(
        "same input must produce same hash",
        encoding="utf-8",
    )

    first_hash = calculate_sha256(file_path)
    second_hash = calculate_sha256(file_path)

    assert first_hash == second_hash
    assert len(first_hash) == 64


def test_calculate_sha256_changes_when_content_changes(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "changing.txt"

    file_path.write_text(
        "version-1",
        encoding="utf-8",
    )
    first_hash = calculate_sha256(file_path)

    file_path.write_text(
        "version-2",
        encoding="utf-8",
    )
    second_hash = calculate_sha256(file_path)

    assert first_hash != second_hash


def test_build_file_metadata_returns_expected_values(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "orders_test.csv"
    content = b"order_id,sku_id\nORDER_001,SKU_001\n"

    file_path.write_bytes(content)

    metadata = build_file_metadata(
        source_name="orders",
        file_path=file_path,
    )

    assert metadata.source_name == "orders"
    assert metadata.file_name == "orders_test.csv"
    assert metadata.file_path == str(file_path.resolve())
    assert metadata.file_size_bytes == len(content)
    assert metadata.file_hash_sha256 == sha256(content).hexdigest()
    assert metadata.file_modified_at.tzinfo is not None


def test_build_file_metadata_accepts_string_path(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "orders_string_path.csv"
    file_path.write_text(
        "order_id\nORDER_001\n",
        encoding="utf-8",
    )

    metadata = build_file_metadata(
        source_name="orders",
        file_path=str(file_path),
    )

    assert metadata.file_name == file_path.name


def test_build_file_metadata_rejects_unknown_source(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "unknown.csv"
    file_path.write_text(
        "sample",
        encoding="utf-8",
    )

    with pytest.raises(
        KeyError,
        match="Unknown source 'unknown_source'",
    ):
        build_file_metadata(
            source_name="unknown_source",
            file_path=file_path,
        )


def test_build_file_metadata_rejects_missing_file(
    tmp_path: Path,
) -> None:
    missing_file = tmp_path / "missing.csv"

    with pytest.raises(
        FileNotFoundError,
        match="Source file does not exist",
    ):
        build_file_metadata(
            source_name="orders",
            file_path=missing_file,
        )


def test_build_file_metadata_rejects_directory(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "not_a_file"
    directory.mkdir()

    with pytest.raises(
        ValueError,
        match="Source path is not a file",
    ):
        build_file_metadata(
            source_name="orders",
            file_path=directory,
        )


@pytest.mark.parametrize(
    "source_name",
    [
        "orders",
        "shop_analytics",
        "campaign_overview",
        "live_performance",
        "product_card_traffic",
        "product_master",
        "sku_master",
    ],
)
def test_build_file_metadata_accepts_all_registered_sources(
    tmp_path: Path,
    source_name: str,
) -> None:
    file_path = tmp_path / f"{source_name}.test"
    file_path.write_text(
        source_name,
        encoding="utf-8",
    )

    metadata = build_file_metadata(
        source_name=source_name,
        file_path=file_path,
    )

    assert metadata.source_name == source_name