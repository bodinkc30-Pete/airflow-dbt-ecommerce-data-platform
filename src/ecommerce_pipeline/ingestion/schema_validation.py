from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from ecommerce_pipeline.ingestion.schema_contracts import (
    RequiredColumn,
    SchemaContract,
    get_schema_contract,
)

SchemaValidationStatus = Literal[
    "VALID",
    "WARNING",
    "INVALID",
]

SchemaIssueSeverity = Literal[
    "WARNING",
    "ERROR",
]


@dataclass(frozen=True)
class SchemaIssue:
    code: str
    severity: SchemaIssueSeverity
    message: str
    column_name: str | None = None


@dataclass(frozen=True)
class SchemaValidationResult:
    source_name: str
    status: SchemaValidationStatus
    observed_column_count: int
    expected_column_count: int
    normalized_columns: tuple[str, ...]
    missing_required_columns: tuple[str, ...]
    duplicate_columns: tuple[str, ...]
    issues: tuple[SchemaIssue, ...]


def normalize_column_name(
    column_name: object,
    *,
    trim: bool = True,
    case_sensitive: bool = False,
) -> str:
    normalized = str(column_name)

    if trim:
        normalized = normalized.strip()

    if not case_sensitive:
        normalized = normalized.casefold()

    return normalized


def normalize_columns(
    columns: Sequence[object],
    contract: SchemaContract,
) -> tuple[str, ...]:
    return tuple(
        normalize_column_name(
            column_name,
            trim=contract.trim_column_names,
            case_sensitive=contract.case_sensitive,
        )
        for column_name in columns
    )


def find_duplicate_columns(
    normalized_columns: Sequence[str],
) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: set[str] = set()

    for column_name in normalized_columns:
        if column_name in seen:
            duplicates.add(column_name)
        else:
            seen.add(column_name)

    return tuple(sorted(duplicates))


def _required_column_is_present(
    required_column: RequiredColumn,
    normalized_columns: set[str],
    contract: SchemaContract,
) -> bool:
    accepted_names = {
        normalize_column_name(
            source_name,
            trim=contract.trim_column_names,
            case_sensitive=contract.case_sensitive,
        )
        for source_name in required_column.accepted_source_names
    }

    return bool(accepted_names & normalized_columns)


def find_missing_required_columns(
    normalized_columns: Sequence[str],
    contract: SchemaContract,
) -> tuple[str, ...]:
    available_columns = set(normalized_columns)

    missing = [
        required_column.canonical_name
        for required_column in contract.required_columns
        if not _required_column_is_present(
            required_column=required_column,
            normalized_columns=available_columns,
            contract=contract,
        )
    ]

    return tuple(sorted(missing))


def validate_schema(
    source_name: str,
    observed_columns: Sequence[object],
) -> SchemaValidationResult:
    contract = get_schema_contract(source_name)

    normalized_columns = normalize_columns(
        columns=observed_columns,
        contract=contract,
    )

    duplicate_columns = find_duplicate_columns(
        normalized_columns
    )

    missing_required_columns = find_missing_required_columns(
        normalized_columns=normalized_columns,
        contract=contract,
    )

    issues: list[SchemaIssue] = []

    observed_column_count = len(observed_columns)
    expected_column_count = contract.expected_column_count

    if observed_column_count != expected_column_count:
        issues.append(
            SchemaIssue(
                code="COLUMN_COUNT_MISMATCH",
                severity="ERROR",
                message=(
                    f"Source '{source_name}' expected "
                    f"{expected_column_count} columns but observed "
                    f"{observed_column_count}"
                ),
            )
        )

    for column_name in duplicate_columns:
        issues.append(
            SchemaIssue(
                code="DUPLICATE_COLUMN",
                severity="ERROR",
                message=(
                    f"Source '{source_name}' contains duplicate "
                    f"column '{column_name}'"
                ),
                column_name=column_name,
            )
        )

    for column_name in missing_required_columns:
        issues.append(
            SchemaIssue(
                code="MISSING_REQUIRED_COLUMN",
                severity="ERROR",
                message=(
                    f"Source '{source_name}' is missing required "
                    f"column '{column_name}'"
                ),
                column_name=column_name,
            )
        )

    if not issues:
        status: SchemaValidationStatus = "VALID"
    elif any(issue.severity == "ERROR" for issue in issues):
        status = "INVALID"
    else:
        status = "WARNING"

    return SchemaValidationResult(
        source_name=source_name,
        status=status,
        observed_column_count=observed_column_count,
        expected_column_count=expected_column_count,
        normalized_columns=normalized_columns,
        missing_required_columns=missing_required_columns,
        duplicate_columns=duplicate_columns,
        issues=tuple(issues),
    )