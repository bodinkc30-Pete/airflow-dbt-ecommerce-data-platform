from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

SHA256_HEX_LENGTH = 64


@dataclass(frozen=True)
class FileFingerprint:
    file_path: Path
    file_size_bytes: int
    sha256_hex: str


def calculate_file_sha256(
    file_path: str | Path,
    chunk_size: int = 1024 * 1024,
) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Source file does not exist: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Source path is not a file: {path}"
        )

    digest = sha256()

    with path.open("rb") as file_handle:
        while chunk := file_handle.read(chunk_size):
            digest.update(chunk)

    return digest.hexdigest()


def validate_sha256_hex(value: str) -> None:
    if len(value) != SHA256_HEX_LENGTH:
        raise ValueError(
            "SHA-256 fingerprint must contain exactly "
            f"{SHA256_HEX_LENGTH} hexadecimal characters"
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(
            "SHA-256 fingerprint must contain only hexadecimal characters"
        ) from exc


def build_file_fingerprint(
    file_path: str | Path,
) -> FileFingerprint:
    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"Source file does not exist: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Source path is not a file: {path}"
        )

    file_hash = calculate_file_sha256(path)
    validate_sha256_hex(file_hash)

    return FileFingerprint(
        file_path=path,
        file_size_bytes=path.stat().st_size,
        sha256_hex=file_hash,
    )


def fingerprints_match(
    first: FileFingerprint,
    second: FileFingerprint,
) -> bool:
    return (
        first.file_size_bytes == second.file_size_bytes
        and first.sha256_hex == second.sha256_hex
    )