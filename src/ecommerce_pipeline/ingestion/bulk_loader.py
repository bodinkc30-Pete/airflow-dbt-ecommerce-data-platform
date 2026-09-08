from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd
from psycopg2 import sql
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import Json, execute_values

from ecommerce_pipeline.ingestion.source_registry import get_source_config


@dataclass(frozen=True)
class LineageMetadata:
    source_file: str
    batch_id: str
    file_hash: str
    pipeline_run_id: int
    ingestion_file_id: int
    ingested_at: datetime | None = None


@dataclass(frozen=True)
class BulkLoadResult:
    source_name: str
    target_table: str
    rows_attempted: int
    rows_loaded: int


def _split_target_table(target_table: str) -> tuple[str, str]:
    parts = target_table.split(".", maxsplit=1)

    if len(parts) != 2:
        raise ValueError(
            "Target table must use schema.table format: "
            f"{target_table}"
        )

    schema_name, table_name = parts

    if not schema_name or not table_name:
        raise ValueError(
            "Target table must use schema.table format: "
            f"{target_table}"
        )

    return schema_name, table_name


def _validate_lineage(lineage: LineageMetadata) -> None:
    if not lineage.source_file.strip():
        raise ValueError("source_file must not be blank")

    if not lineage.batch_id.strip():
        raise ValueError("batch_id must not be blank")

    if len(lineage.file_hash) != 64:
        raise ValueError(
            "file_hash must contain exactly 64 characters"
        )

    try:
        int(lineage.file_hash, 16)
    except ValueError as exc:
        raise ValueError(
            "file_hash must contain only hexadecimal characters"
        ) from exc

    if lineage.pipeline_run_id <= 0:
        raise ValueError("pipeline_run_id must be positive")

    if lineage.ingestion_file_id <= 0:
        raise ValueError("ingestion_file_id must be positive")


def _normalize_dataframe_nulls(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    return dataframe.astype(object).where(
        pd.notna(dataframe),
        None,
    )


def prepare_raw_dataframe(
    dataframe: pd.DataFrame,
    *,
    column_mapping: Mapping[str, str],
    lineage: LineageMetadata,
    source_row_start: int = 1,
) -> pd.DataFrame:
    _validate_lineage(lineage)

    if source_row_start <= 0:
        raise ValueError("source_row_start must be positive")

    missing_source_columns = sorted(
        source_column
        for source_column in column_mapping
        if source_column not in dataframe.columns
    )

    if missing_source_columns:
        missing = ", ".join(missing_source_columns)
        raise ValueError(
            "Source dataframe is missing mapped columns: "
            f"{missing}"
        )

    destination_columns = list(column_mapping.values())

    if len(destination_columns) != len(set(destination_columns)):
        raise ValueError(
            "column_mapping contains duplicate destination columns"
        )

    prepared = dataframe[
        list(column_mapping.keys())
    ].rename(
        columns=dict(column_mapping)
    ).copy()

    prepared = _normalize_dataframe_nulls(prepared)

    prepared["_source_file"] = lineage.source_file
    prepared["_source_row_number"] = range(
        source_row_start,
        source_row_start + len(prepared),
    )
    prepared["_batch_id"] = lineage.batch_id
    prepared["_file_hash"] = lineage.file_hash
    prepared["_ingested_at"] = (
        lineage.ingested_at
        if lineage.ingested_at is not None
        else datetime.now(UTC)
    )
    prepared["_pipeline_run_id"] = lineage.pipeline_run_id
    prepared["_ingestion_file_id"] = lineage.ingestion_file_id

    return prepared


def prepare_influencer_roster_dataframe(
    dataframe: pd.DataFrame,
    *,
    column_mapping: Mapping[str, str],
    lineage: LineageMetadata,
    source_row_start: int = 1,
) -> pd.DataFrame:
    explicit_columns = (
        "influencer_name",
        "follower_count",
        "engagement_rate",
        "budget",
    )
    if set(column_mapping.values()) != set(explicit_columns):
        raise ValueError(
            "Influencer roster mapping must define exactly: "
            + ", ".join(explicit_columns)
        )

    prepared = prepare_raw_dataframe(
        dataframe=dataframe,
        column_mapping=column_mapping,
        lineage=lineage,
        source_row_start=source_row_start,
    )
    lineage_columns = (
        "_source_file",
        "_source_row_number",
        "_batch_id",
        "_file_hash",
        "_ingested_at",
        "_pipeline_run_id",
        "_ingestion_file_id",
    )
    prepared = prepared.loc[:, [*explicit_columns, *lineage_columns]]
    normalized_source = _normalize_dataframe_nulls(dataframe)
    payloads = [
        Json(
            {
                str(column): (None if value is None else str(value))
                for column, value in row.items()
            }
        )
        for row in normalized_source.to_dict(orient="records")
    ]
    prepared.insert(len(explicit_columns), "source_payload", payloads)
    return prepared


def prepare_product_master_dataframe(
    dataframe: pd.DataFrame,
    *,
    column_mapping: Mapping[str, str],
    lineage: LineageMetadata,
    source_row_start: int = 1,
) -> pd.DataFrame:
    explicit_columns = (
        "product_id",
        "product_name",
        "gmv_tier",
        "product_status",
    )
    destination_columns = tuple(column_mapping.values())

    if set(destination_columns) != set(explicit_columns):
        raise ValueError(
            "Product Master mapping must define exactly: "
            + ", ".join(explicit_columns)
        )

    prepared = prepare_raw_dataframe(
        dataframe=dataframe,
        column_mapping=column_mapping,
        lineage=lineage,
        source_row_start=source_row_start,
    )

    lineage_columns = (
        "_source_file",
        "_source_row_number",
        "_batch_id",
        "_file_hash",
        "_ingested_at",
        "_pipeline_run_id",
        "_ingestion_file_id",
    )
    prepared = prepared.loc[:, [*explicit_columns, *lineage_columns]]

    normalized_source = _normalize_dataframe_nulls(dataframe)
    payloads = [
        Json(
            {
                str(column): (None if value is None else str(value))
                for column, value in row.items()
            }
        )
        for row in normalized_source.to_dict(orient="records")
    ]
    prepared.insert(len(explicit_columns), "source_payload", payloads)

    return prepared


def _dataframe_rows(
    dataframe: pd.DataFrame,
    columns: Sequence[str],
) -> list[tuple[object, ...]]:
    return [
        tuple(row)
        for row in dataframe.loc[:, columns].itertuples(
            index=False,
            name=None,
        )
    ]


def bulk_insert_dataframe(
    connection: PgConnection,
    *,
    target_table: str,
    dataframe: pd.DataFrame,
    page_size: int = 1000,
) -> int:
    if page_size <= 0:
        raise ValueError("page_size must be positive")

    if dataframe.empty:
        return 0

    if dataframe.columns.empty:
        raise ValueError(
            "Dataframe must contain at least one column"
        )

    schema_name, table_name = _split_target_table(
        target_table
    )

    columns = [str(column) for column in dataframe.columns]

    if len(columns) != len(set(columns)):
        raise ValueError(
            "Dataframe contains duplicate destination columns"
        )

    rows = _dataframe_rows(
        dataframe=dataframe,
        columns=columns,
    )

    insert_query = sql.SQL(
        "INSERT INTO {}.{} ({}) VALUES %s"
    ).format(
        sql.Identifier(schema_name),
        sql.Identifier(table_name),
        sql.SQL(", ").join(
            sql.Identifier(column)
            for column in columns
        ),
    )

    with connection.cursor() as cursor:
        execute_values(
            cursor,
            insert_query.as_string(connection),
            rows,
            page_size=page_size,
        )

    return len(rows)


def bulk_load_source(
    connection: PgConnection,
    *,
    source_name: str,
    dataframe: pd.DataFrame,
    column_mapping: Mapping[str, str],
    lineage: LineageMetadata,
    source_row_start: int = 1,
    page_size: int = 1000,
) -> BulkLoadResult:
    source_config = get_source_config(source_name)

    if source_name == "influencer_roster":
        prepared = prepare_influencer_roster_dataframe(
            dataframe=dataframe,
            column_mapping=column_mapping,
            lineage=lineage,
            source_row_start=source_row_start,
        )
    elif source_name == "product_master":
        prepared = prepare_product_master_dataframe(
            dataframe=dataframe,
            column_mapping=column_mapping,
            lineage=lineage,
            source_row_start=source_row_start,
        )
    else:
        prepared = prepare_raw_dataframe(
            dataframe=dataframe,
            column_mapping=column_mapping,
            lineage=lineage,
            source_row_start=source_row_start,
        )

    rows_loaded = bulk_insert_dataframe(
        connection=connection,
        target_table=source_config.target_table,
        dataframe=prepared,
        page_size=page_size,
    )

    return BulkLoadResult(
        source_name=source_name,
        target_table=source_config.target_table,
        rows_attempted=len(prepared),
        rows_loaded=rows_loaded,
    )
