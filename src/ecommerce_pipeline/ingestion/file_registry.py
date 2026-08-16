from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO

import psycopg2
from psycopg2.extensions import connection as PgConnection

from ecommerce_pipeline.ingestion.source_registry import get_source_config


@dataclass(frozen=True)
class FileMetadata:
    source_name: str
    file_name: str
    file_path: str
    file_size_bytes: int
    file_modified_at: datetime
    file_hash_sha256: str


@dataclass(frozen=True)
class FileRegistrationResult:
    ingestion_file_id: int
    source_name: str
    file_hash_sha256: str
    status: str
    is_duplicate: bool


def _hash_stream(stream: BinaryIO, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()

    while chunk := stream.read(chunk_size):
        digest.update(chunk)

    return digest.hexdigest()


def calculate_sha256(file_path: str | Path) -> str:
    path = Path(file_path)

    with path.open("rb") as file_handle:
        return _hash_stream(file_handle)


def build_file_metadata(
    source_name: str,
    file_path: str | Path,
) -> FileMetadata:
    get_source_config(source_name)

    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Source file does not exist: {path}")

    if not path.is_file():
        raise ValueError(f"Source path is not a file: {path}")

    stat = path.stat()

    return FileMetadata(
        source_name=source_name,
        file_name=path.name,
        file_path=str(path),
        file_size_bytes=stat.st_size,
        file_modified_at=datetime.fromtimestamp(
            stat.st_mtime
        ).astimezone(),
        file_hash_sha256=calculate_sha256(path),
    )


def find_registered_file(
    connection: PgConnection,
    source_name: str,
    file_hash_sha256: str,
) -> FileRegistrationResult | None:
    query = """
        SELECT
            ingestion_file_id,
            source_name,
            file_hash_sha256,
            status
        FROM audit.ingestion_files
        WHERE source_name = %s
          AND file_hash_sha256 = %s
        LIMIT 1;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                source_name,
                file_hash_sha256,
            ),
        )

        row = cursor.fetchone()

    if row is None:
        return None

    return FileRegistrationResult(
        ingestion_file_id=row[0],
        source_name=row[1],
        file_hash_sha256=row[2].strip(),
        status=row[3],
        is_duplicate=True,
    )


def register_file(
    connection: PgConnection,
    ingestion_run_id: int,
    metadata: FileMetadata,
) -> FileRegistrationResult:
    existing = find_registered_file(
        connection=connection,
        source_name=metadata.source_name,
        file_hash_sha256=metadata.file_hash_sha256,
    )

    if existing is not None:
        return existing

    query = """
        INSERT INTO audit.ingestion_files (
            ingestion_run_id,
            source_name,
            file_name,
            file_path,
            file_size_bytes,
            file_modified_at,
            file_hash_sha256,
            status
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            'discovered'
        )
        RETURNING
            ingestion_file_id,
            source_name,
            file_hash_sha256,
            status;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                ingestion_run_id,
                metadata.source_name,
                metadata.file_name,
                metadata.file_path,
                metadata.file_size_bytes,
                metadata.file_modified_at,
                metadata.file_hash_sha256,
            ),
        )

        row = cursor.fetchone()

    return FileRegistrationResult(
        ingestion_file_id=row[0],
        source_name=row[1],
        file_hash_sha256=row[2].strip(),
        status=row[3],
        is_duplicate=False,
    )


def connect_postgres(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
) -> PgConnection:
    return psycopg2.connect(
        host=host,
        port=port,
        dbname=database,
        user=user,
        password=password,
    )