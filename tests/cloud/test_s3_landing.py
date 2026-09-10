from pathlib import Path

import pytest

from ecommerce_pipeline.cloud.s3_landing import sync_s3_landing


class _FakePaginator:
    def __init__(self, pages: list[dict[str, object]]) -> None:
        self.pages = pages

    def paginate(self, **kwargs: object) -> list[dict[str, object]]:
        assert kwargs["Bucket"] == "project06-bucket"
        assert kwargs["Prefix"] == "landing/"
        return self.pages


class _FakeS3Client:
    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        self.downloads: list[tuple[str, str, str]] = []

    def get_paginator(self, name: str) -> _FakePaginator:
        assert name == "list_objects_v2"
        return _FakePaginator([{"Contents": [{"Key": key} for key in self.keys]}])

    def download_file(self, bucket: str, key: str, target: str) -> None:
        Path(target).write_text(f"{bucket}:{key}", encoding="utf-8")
        self.downloads.append((bucket, key, target))


def test_sync_s3_landing_downloads_supported_files_and_removes_stale(
    tmp_path: Path,
) -> None:
    stale = tmp_path / "stale.csv"
    stale.write_text("old", encoding="utf-8")
    client = _FakeS3Client(
        [
            "landing/Shop-Analytics_Key-metrics_20260910.xlsx",
            "landing/คำสั่งซื้อ_20260910.csv",
            "landing/readme.txt",
        ]
    )

    result = sync_s3_landing(
        bucket="project06-bucket",
        prefix="landing",
        destination=tmp_path,
        s3_client=client,
    )

    assert [path.name for path in result] == [
        "Shop-Analytics_Key-metrics_20260910.xlsx",
        "คำสั่งซื้อ_20260910.csv",
    ]

    assert stale.exists() is False
    assert len(client.downloads) == 2


def test_sync_s3_landing_rejects_duplicate_basenames(tmp_path: Path) -> None:
    client = _FakeS3Client(
        [
            "landing/a/product_sku_list.xlsx",
            "landing/b/product_sku_list.xlsx",
        ]
    )

    with pytest.raises(ValueError, match="duplicate file names"):
        sync_s3_landing(
            bucket="project06-bucket",
            prefix="landing",
            destination=tmp_path,
            s3_client=client,
        )


def test_sync_s3_landing_rejects_blank_bucket(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="bucket must not be blank"):
        sync_s3_landing(
            bucket=" ",
            prefix="landing",
            destination=tmp_path,
            s3_client=_FakeS3Client([]),
        )
