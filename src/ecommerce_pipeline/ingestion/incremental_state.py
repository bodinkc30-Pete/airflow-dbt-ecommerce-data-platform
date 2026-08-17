from dataclasses import dataclass
from typing import Literal

from psycopg2.extensions import connection as PgConnection

WatermarkType = Literal[
    "timestamp",
    "date",
    "integer",
    "string",
    "file",
]


@dataclass(frozen=True)
class WatermarkState:
    source_name: str
    watermark_type: WatermarkType
    watermark_value: str | None
    last_successful_run_id: int | None
    last_successful_file_id: int | None


def get_watermark_state(
    connection: PgConnection,
    *,
    source_name: str,
) -> WatermarkState | None:
    query = """
        SELECT
            source_name,
            watermark_type,
            watermark_value,
            last_successful_run_id,
            last_successful_file_id
        FROM audit.source_watermarks
        WHERE source_name = %s;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (source_name,),
        )
        row = cursor.fetchone()

    if row is None:
        return None

    return WatermarkState(
        source_name=row[0],
        watermark_type=row[1],
        watermark_value=row[2],
        last_successful_run_id=row[3],
        last_successful_file_id=row[4],
    )


def upsert_watermark_state(
    connection: PgConnection,
    *,
    source_name: str,
    watermark_type: WatermarkType,
    watermark_value: str | None,
    last_successful_run_id: int | None,
    last_successful_file_id: int | None,
) -> WatermarkState:
    query = """
        INSERT INTO audit.source_watermarks (
            source_name,
            watermark_type,
            watermark_value,
            last_successful_run_id,
            last_successful_file_id
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s
        )
        ON CONFLICT (source_name)
        DO UPDATE SET
            watermark_type = EXCLUDED.watermark_type,
            watermark_value = EXCLUDED.watermark_value,
            last_successful_run_id = EXCLUDED.last_successful_run_id,
            last_successful_file_id = EXCLUDED.last_successful_file_id,
            updated_at = CURRENT_TIMESTAMP
        RETURNING
            source_name,
            watermark_type,
            watermark_value,
            last_successful_run_id,
            last_successful_file_id;
    """

    with connection.cursor() as cursor:
        cursor.execute(
            query,
            (
                source_name,
                watermark_type,
                watermark_value,
                last_successful_run_id,
                last_successful_file_id,
            ),
        )
        row = cursor.fetchone()

    return WatermarkState(
        source_name=row[0],
        watermark_type=row[1],
        watermark_value=row[2],
        last_successful_run_id=row[3],
        last_successful_file_id=row[4],
    )
