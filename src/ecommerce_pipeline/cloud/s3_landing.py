from __future__ import annotations

from pathlib import Path
from typing import Any

_ALLOWED_SUFFIXES = {".csv", ".xlsx"}


def _get_s3_client() -> Any:
    import boto3

    return boto3.client("s3")


def _normalize_prefix(prefix: str) -> str:
    normalized = prefix.strip().strip("/")
    return f"{normalized}/" if normalized else ""


def _safe_target(destination: Path, file_name: str) -> Path:
    if not file_name or file_name in {".", ".."}:
        raise ValueError("S3 object must have a valid file name")

    target = (destination / file_name).resolve()
    if target.parent != destination:
        raise ValueError("S3 object file name escaped the staging directory")

    return target


def sync_s3_landing(
    *,
    bucket: str,
    prefix: str,
    destination: str | Path,
    s3_client: Any | None = None,
) -> tuple[Path, ...]:
    """Mirror supported S3 landing objects into a dedicated local directory."""
    if not bucket.strip():
        raise ValueError("S3 bucket must not be blank")

    destination_path = Path(destination).resolve()
    destination_path.mkdir(parents=True, exist_ok=True)
    client = s3_client or _get_s3_client()
    normalized_prefix = _normalize_prefix(prefix)

    expected: dict[Path, str] = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=normalized_prefix):
        for item in page.get("Contents", []):
            key = str(item["Key"])
            file_name = Path(key).name
            suffix = Path(file_name).suffix.lower()
            if suffix not in _ALLOWED_SUFFIXES:
                continue

            target = _safe_target(destination_path, file_name)
            if target in expected:
                raise ValueError(
                    "S3 landing prefix contains duplicate file names: "
                    f"{file_name}"
                )
            expected[target] = key

    for target, key in sorted(expected.items(), key=lambda pair: pair[0].name):
        temporary = target.with_name(f".{target.name}.part")
        client.download_file(bucket, key, str(temporary))
        temporary.replace(target)

    for existing in destination_path.iterdir():
        if not existing.is_file():
            continue
        if existing.suffix.lower() not in _ALLOWED_SUFFIXES:
            continue
        if existing not in expected:
            existing.unlink()

    return tuple(sorted(expected, key=lambda path: path.name.casefold()))
