from dataclasses import dataclass
from typing import Literal

import pandas as pd
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import Json

QualityStatus = Literal["pass", "fail", "warning", "skipped"]
QualityCategory = Literal[
    "file",
    "schema",
    "record",
    "identifier",
    "relationship",
    "business_rule",
    "reconciliation",
]


@dataclass(frozen=True)
class DataQualityCheckResult:
    check_name: str
    check_category: QualityCategory
    status: QualityStatus
    rows_checked: int
    rows_failed: int
    expected_value: str | None = None
    observed_value: str | None = None
    failure_reason: str | None = None
    details: dict[str, object] | None = None


def _text_series(dataframe: pd.DataFrame, column: str) -> pd.Series:
    return dataframe[column].astype(str).str.strip()


def _warning_or_pass(failed: int) -> QualityStatus:
    return "warning" if failed else "pass"


def _numeric_non_negative_result(
    dataframe: pd.DataFrame, *, source_column: str, check_name: str
) -> DataQualityCheckResult:
    values = _text_series(dataframe, source_column).str.replace(",", "", regex=False)
    numeric = pd.to_numeric(values.where(values.ne("")), errors="coerce")
    failed_mask = values.eq("") | numeric.isna() | numeric.lt(0)
    failed = int(failed_mask.sum())
    return DataQualityCheckResult(
        check_name=check_name,
        check_category="record",
        status=_warning_or_pass(failed),
        rows_checked=len(dataframe),
        rows_failed=failed,
        expected_value="numeric value >= 0",
        observed_value=f"{failed} invalid rows",
        failure_reason=("Non-numeric, blank, or negative values detected" if failed else None),
    )


def evaluate_influencer_roster_quality(
    dataframe: pd.DataFrame,
) -> tuple[DataQualityCheckResult, ...]:
    identity = _text_series(dataframe, "Influencer")
    blank_mask = identity.eq("")
    blank_count = int(blank_mask.sum())
    identity_result = DataQualityCheckResult(
        check_name="influencer_identity_not_blank",
        check_category="identifier",
        status="fail" if blank_count else "pass",
        rows_checked=len(dataframe),
        rows_failed=blank_count,
        expected_value="0 blank identities",
        observed_value=f"{blank_count} blank identities",
        failure_reason=("Blank influencer identity detected" if blank_count else None),
    )

    normalized = identity.str.casefold()
    duplicate_mask = normalized.ne("") & normalized.duplicated(keep=False)
    duplicate_rows = int(duplicate_mask.sum())
    duplicate_keys = int(normalized[duplicate_mask].nunique())
    duplicate_result = DataQualityCheckResult(
        check_name="influencer_identity_duplicate",
        check_category="identifier",
        status=_warning_or_pass(duplicate_rows),
        rows_checked=len(dataframe),
        rows_failed=duplicate_rows,
        expected_value="unique normalized influencer identity",
        observed_value=f"{duplicate_rows} duplicate rows",
        failure_reason=(
            "Duplicate normalized influencer identities detected" if duplicate_rows else None
        ),
        details={"duplicate_key_count": duplicate_keys},
    )

    follower_result = _numeric_non_negative_result(
        dataframe,
        source_column="Follower",
        check_name="follower_non_negative_numeric",
    )
    budget_result = _numeric_non_negative_result(
        dataframe,
        source_column="BUDGET",
        check_name="budget_non_negative_numeric",
    )

    engagement_text = _text_series(dataframe, "Engangement Rate%")
    stripped = engagement_text.str.removesuffix("%")
    engagement = pd.to_numeric(stripped.where(stripped.ne("")), errors="coerce")
    engagement_failed = (
        engagement_text.eq("") | engagement.isna() | engagement.lt(0) | engagement.gt(100)
    )
    engagement_failed_count = int(engagement_failed.sum())
    engagement_result = DataQualityCheckResult(
        check_name="engagement_rate_parseable_range",
        check_category="record",
        status=_warning_or_pass(engagement_failed_count),
        rows_checked=len(dataframe),
        rows_failed=engagement_failed_count,
        expected_value="parseable percentage in range 0..100",
        observed_value=f"{engagement_failed_count} invalid rows",
        failure_reason=(
            "Unparseable, blank, or out-of-range engagement rate detected"
            if engagement_failed_count
            else None
        ),
    )

    return (identity_result, duplicate_result, follower_result, budget_result, engagement_result)


def evaluate_source_quality(
    source_name: str, dataframe: pd.DataFrame
) -> tuple[DataQualityCheckResult, ...]:
    if source_name == "influencer_roster":
        return evaluate_influencer_roster_quality(dataframe)
    return ()


def has_blocking_quality_failures(
    results: tuple[DataQualityCheckResult, ...],
) -> bool:
    return any(result.status == "fail" for result in results)


def record_data_quality_results(
    connection: PgConnection,
    *,
    ingestion_run_id: int | None,
    ingestion_file_id: int | None,
    source_name: str,
    results: tuple[DataQualityCheckResult, ...],
) -> tuple[int, ...]:
    if not results:
        return ()
    query = """
        INSERT INTO audit.data_quality_results (
            ingestion_run_id, ingestion_file_id, source_name, check_name,
            check_category, status, rows_checked, rows_failed, expected_value,
            observed_value, failure_reason, details
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING data_quality_result_id;
    """
    ids: list[int] = []
    with connection.cursor() as cursor:
        for result in results:
            cursor.execute(
                query,
                (
                    ingestion_run_id,
                    ingestion_file_id,
                    source_name,
                    result.check_name,
                    result.check_category,
                    result.status,
                    result.rows_checked,
                    result.rows_failed,
                    result.expected_value,
                    result.observed_value,
                    result.failure_reason,
                    Json(result.details or {}),
                ),
            )
            ids.append(cursor.fetchone()[0])
    return tuple(ids)
