from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from ecommerce_pipeline.ingestion.schema_contracts import get_schema_contract
from ecommerce_pipeline.ingestion.source_registry import get_source_config

ExtractionEngine = Literal[
    "pandas_csv",
    "pandas_excel",
    "product_master_two_level",
]


@dataclass(frozen=True)
class ExtractionResult:
    source_name: str
    file_path: Path
    engine: ExtractionEngine
    row_count: int
    column_count: int
    columns: tuple[str, ...]
    dataframe: pd.DataFrame


def _validate_source_file(file_path: str | Path) -> Path:
    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"Source file does not exist: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Source path is not a file: {path}"
        )

    if path.stat().st_size == 0:
        raise ValueError(
            f"Source file is empty: {path}"
        )

    return path


def _clean_header_value(value: object) -> str:
    if pd.isna(value):
        return ""

    return str(value).strip()


def _deduplicate_names(names: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    result: list[str] = []

    for name in names:
        base_name = name or "unnamed"

        if base_name not in counts:
            counts[base_name] = 0
            result.append(base_name)
            continue

        counts[base_name] += 1
        result.append(f"{base_name}__{counts[base_name]}")

    return result


def canonicalize_product_master_headers(
    group_headers: list[object],
    metric_headers: list[object],
) -> tuple[str, ...]:
    if len(group_headers) != len(metric_headers):
        raise ValueError(
            "Product Master group and metric header lengths do not match"
        )

    canonical_names: list[str] = []
    current_group = ""

    for group_value, metric_value in zip(
        group_headers,
        metric_headers,
        strict=True,
    ):
        group_name = _clean_header_value(group_value)
        metric_name = _clean_header_value(metric_value)

        if group_name:
            current_group = group_name

        if current_group and metric_name:
            canonical_name = f"{current_group}::{metric_name}"
        elif metric_name:
            canonical_name = metric_name
        elif current_group:
            canonical_name = current_group
        else:
            canonical_name = "unnamed"

        canonical_names.append(canonical_name)

    return tuple(_deduplicate_names(canonical_names))


def _extract_csv(
    path: Path,
    header_row: int,
) -> pd.DataFrame:
    return pd.read_csv(
        path,
        header=header_row,
        dtype=str,
        keep_default_na=False,
    )


def _extract_excel_flat(
    path: Path,
    sheet_name: str | None,
    header_row: int,
) -> pd.DataFrame:
    return pd.read_excel(
        path,
        sheet_name=sheet_name or 0,
        header=header_row,
        dtype=str,
        keep_default_na=False,
        engine="openpyxl",
    )


def _extract_product_master_two_level(
    path: Path,
    sheet_name: str | None,
) -> pd.DataFrame:
    raw = pd.read_excel(
        path,
        sheet_name=sheet_name or 0,
        header=None,
        dtype=object,
        engine="openpyxl",
    )

    if raw.shape[0] < 4:
        raise ValueError(
            "Product Master must contain at least 4 rows "
            "for two-level header extraction"
        )

    group_headers = raw.iloc[2].tolist()
    metric_headers = raw.iloc[3].tolist()

    canonical_columns = canonicalize_product_master_headers(
        group_headers=group_headers,
        metric_headers=metric_headers,
    )

    data = raw.iloc[4:].copy()
    data.columns = canonical_columns
    data.reset_index(drop=True, inplace=True)

    return data


def _trim_influencer_roster_trailing_blank_rows(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    identity_column = "Influencer"
    if identity_column not in dataframe.columns:
        return dataframe

    non_blank = dataframe[identity_column].astype(str).str.strip().ne("")
    if not non_blank.any():
        return dataframe.iloc[0:0].copy()

    last_valid_position = int(non_blank.to_numpy().nonzero()[0][-1])
    return dataframe.iloc[: last_valid_position + 1].copy()


def extract_source_file(
    source_name: str,
    file_path: str | Path,
) -> ExtractionResult:
    source_config = get_source_config(source_name)
    schema_contract = get_schema_contract(source_name)
    path = _validate_source_file(file_path)

    if source_config.file_format == "csv":
        engine: ExtractionEngine = "pandas_csv"
        dataframe = _extract_csv(
            path=path,
            header_row=source_config.header_row,
        )
    elif schema_contract.header_strategy == "product_master_two_level":
        engine = "product_master_two_level"
        dataframe = _extract_product_master_two_level(
            path=path,
            sheet_name=source_config.sheet_name,
        )
    elif source_config.file_format == "xlsx":
        engine = "pandas_excel"
        dataframe = _extract_excel_flat(
            path=path,
            sheet_name=source_config.sheet_name,
            header_row=source_config.header_row,
        )
    else:
        raise ValueError(
            f"Unsupported file format for source "
            f"'{source_name}': {source_config.file_format}"
        )

    dataframe.columns = tuple(
        str(column).strip()
        for column in dataframe.columns
    )

    campaign_date_header = "\u0e15\u0e32\u0e21\u0e27\u0e31\u0e19"
    if source_name == "influencer_roster":
        dataframe = _trim_influencer_roster_trailing_blank_rows(dataframe)

    if (
        source_name == "campaign_overview"
        and campaign_date_header in dataframe.columns
    ):
        footer_mask = (
            dataframe[campaign_date_header]
            .astype(str)
            .str.strip()
            .eq("-")
        )
        dataframe = dataframe.loc[~footer_mask].copy()

    return ExtractionResult(
        source_name=source_name,
        file_path=path,
        engine=engine,
        row_count=len(dataframe),
        column_count=len(dataframe.columns),
        columns=tuple(dataframe.columns),
        dataframe=dataframe,
    )
