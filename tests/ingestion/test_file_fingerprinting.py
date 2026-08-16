from hashlib import sha256
from pathlib import Path

import pytest

from ecommerce_pipeline.ingestion.file_fingerprinting import (
    FileFingerprint,
    build_file_fingerprint,
    calculate_file_sha256,
    fingerprints_match,
    validate_sha256_hex,
)


def test_calculate_file_sha256_matches_expected_hash(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "sample.bin"
    content = b"project-06-file-fingerprinting"

    file_path.write_bytes(content)

    expected_hash = sha256(content).hexdigest()

    assert calculate_file_sha256(file_path) == expected_hash


def test_calculate_file_sha256_is_deterministic(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "deterministic.txt"
    file_path.write_text(
        "same content",
        encoding="utf-8",
    )

    first_hash = calculate_file_sha256(file_path)
    second_hash = calculate_file_sha256(file_path)

    assert first_hash == second_hash
    assert len(first_hash) == 64


def test_calculate_file_sha256_changes_when_content_changes(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "changing.txt"

    file_path.write_text(
        "version-1",
        encoding="utf-8",
    )
    first_hash = calculate_file_sha256(file_path)

    file_path.write_text(
        "version-2",
        encoding="utf-8",
    )
    second_hash = calculate_file_sha256(file_path)

    assert first_hash != second_hash


def test_calculate_file_sha256_rejects_missing_file(
    tmp_path: Path,
) -> None:
    missing_file = tmp_path / "missing.csv"

    with pytest.raises(
        FileNotFoundError,
        match="Source file does not exist",
    ):
        calculate_file_sha256(missing_file)


def test_calculate_file_sha256_rejects_directory(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "directory"
    directory.mkdir()

    with pytest.raises(
        ValueError,
        match="Source path is not a file",
    ):
        calculate_file_sha256(directory)


def test_validate_sha256_hex_accepts_valid_hash() -> None:
    valid_hash = "a" * 64

    validate_sha256_hex(valid_hash)


def test_validate_sha256_hex_rejects_invalid_length() -> None:
    with pytest.raises(
        ValueError,
        match="exactly 64 hexadecimal characters",
    ):
        validate_sha256_hex("a" * 63)


def test_validate_sha256_hex_rejects_non_hex_characters() -> None:
    invalid_hash = "g" * 64

    with pytest.raises(
        ValueError,
        match="only hexadecimal characters",
    ):
        validate_sha256_hex(invalid_hash)


def test_build_file_fingerprint_returns_expected_values(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "orders.csv"
    content = b"order_id,sku_id\nORDER_001,SKU_001\n"

    file_path.write_bytes(content)

    fingerprint = build_file_fingerprint(file_path)

    assert fingerprint.file_path == file_path.resolve()
    assert fingerprint.file_size_bytes == len(content)
    assert fingerprint.sha256_hex == sha256(content).hexdigest()


def test_build_file_fingerprint_accepts_string_path(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "string-path.txt"
    file_path.write_text(
        "sample",
        encoding="utf-8",
    )

    fingerprint = build_file_fingerprint(str(file_path))

    assert fingerprint.file_path == file_path.resolve()


def test_build_file_fingerprint_rejects_missing_file(
    tmp_path: Path,
) -> None:
    missing_file = tmp_path / "missing.xlsx"

    with pytest.raises(
        FileNotFoundError,
        match="Source file does not exist",
    ):
        build_file_fingerprint(missing_file)


def test_build_file_fingerprint_rejects_directory(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "not-a-file"
    directory.mkdir()

    with pytest.raises(
        ValueError,
        match="Source path is not a file",
    ):
        build_file_fingerprint(directory)


def test_fingerprints_match_when_hash_and_size_match() -> None:
    first = FileFingerprint(
        file_path=Path("first.csv"),
        file_size_bytes=100,
        sha256_hex="a" * 64,
    )

    second = FileFingerprint(
        file_path=Path("second.csv"),
        file_size_bytes=100,
        sha256_hex="a" * 64,
    )

    assert fingerprints_match(first, second) is True


def test_fingerprints_do_not_match_when_hash_differs() -> None:
    first = FileFingerprint(
        file_path=Path("first.csv"),
        file_size_bytes=100,
        sha256_hex="a" * 64,
    )

    second = FileFingerprint(
        file_path=Path("second.csv"),
        file_size_bytes=100,
        sha256_hex="b" * 64,
    )

    assert fingerprints_match(first, second) is False


def test_fingerprints_do_not_match_when_size_differs() -> None:
    first = FileFingerprint(
        file_path=Path("first.csv"),
        file_size_bytes=100,
        sha256_hex="a" * 64,
    )

    second = FileFingerprint(
        file_path=Path("second.csv"),
        file_size_bytes=101,
        sha256_hex="a" * 64,
    )

    assert fingerprints_match(first, second) is False


def test_rebuilding_same_file_produces_same_fingerprint(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "same-file.csv"
    file_path.write_bytes(b"same-content")

    first = build_file_fingerprint(file_path)
    second = build_file_fingerprint(file_path)

    assert fingerprints_match(first, second) is True


def test_file_change_produces_different_fingerprint(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "changed-file.csv"

    file_path.write_bytes(b"before")
    before = build_file_fingerprint(file_path)

    file_path.write_bytes(b"after-change")
    after = build_file_fingerprint(file_path)

    assert fingerprints_match(before, after) is False