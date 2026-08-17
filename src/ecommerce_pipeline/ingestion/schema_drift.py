from dataclasses import dataclass
from typing import Literal

from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import Json

from ecommerce_pipeline.ingestion.schema_validation import (
    SchemaIssue,
    SchemaValidationResult,
)

SchemaEventType = Literal[
    "missing_column",
    "unexpected_column",
    "data_type_change",
    "column_order_change",
    "nullable_change",
    "schema_version_change",
    "other",
]

SchemaEventSeverity = Literal[
    "info",
    "warning",
    "error",
    "critical",
]


@dataclass(frozen=True)
class SchemaDriftEvent:
    source_name: str
    event_type: SchemaEventType
    severity: SchemaEventSeverity
    column_name: str | None
    expected_value: str | None
    observed_value: str | None
    details: dict[str, object]


def _map_severity(issue: SchemaIssue) -> SchemaEventSeverity:
    if issue.severity == "WARNING":
        return "warning"

    return "error"


def _classify_issue(
    result: SchemaValidationResult,
    issue: SchemaIssue,
) -> SchemaDriftEvent:
    details: dict[str, object] = {
        "validation_issue_code": issue.code,
        "validation_message": issue.message,
        "validation_status": result.status,
    }

    if issue.code == "MISSING_REQUIRED_COLUMN":
        return SchemaDriftEvent(
            source_name=result.source_name,
            event_type="missing_column",
            severity=_map_severity(issue),
            column_name=issue.column_name,
            expected_value="required",
            observed_value="missing",
            details=details,
        )

    if issue.code == "COLUMN_COUNT_MISMATCH":
        return SchemaDriftEvent(
            source_name=result.source_name,
            event_type="other",
            severity=_map_severity(issue),
            column_name=None,
            expected_value=str(result.expected_column_count),
            observed_value=str(result.observed_column_count),
            details=details,
        )

    if issue.code == "DUPLICATE_COLUMN":
        return SchemaDriftEvent(
            source_name=result.source_name,
            event_type="other",
            severity=_map_severity(issue),
            column_name=issue.column_name,
            expected_value="unique_column_name",
            observed_value="duplicate",
            details=details,
        )

    return SchemaDriftEvent(
        source_name=result.source_name,
        event_type="other",
        severity=_map_severity(issue),
        column_name=issue.column_name,
        expected_value=None,
        observed_value=None,
        details=details,
    )


def classify_schema_drift(
    result: SchemaValidationResult,
) -> tuple[SchemaDriftEvent, ...]:
    """
    Convert schema-validation issues into auditable schema-drift events.

    Classification is intentionally conservative. The function does not
    invent unexpected-column, type-change, order-change, nullable-change,
    or version-change evidence that the current validator does not produce.
    """

    return tuple(
        _classify_issue(
            result=result,
            issue=issue,
        )
        for issue in result.issues
    )


def record_schema_events(
    connection: PgConnection,
    *,
    ingestion_run_id: int | None,
    ingestion_file_id: int | None,
    events: tuple[SchemaDriftEvent, ...],
) -> tuple[int, ...]:
    """
    Persist schema-drift events and return generated IDs.

    Transaction ownership remains with the caller. This function never
    commits or rolls back the supplied connection.
    """

    if not events:
        return ()

    query = """
        INSERT INTO audit.schema_events (
            ingestion_run_id,
            ingestion_file_id,
            source_name,
            event_type,
            column_name,
            expected_value,
            observed_value,
            severity,
            details
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        RETURNING schema_event_id;
    """

    event_ids: list[int] = []

    with connection.cursor() as cursor:
        for event in events:
            cursor.execute(
                query,
                (
                    ingestion_run_id,
                    ingestion_file_id,
                    event.source_name,
                    event.event_type,
                    event.column_name,
                    event.expected_value,
                    event.observed_value,
                    event.severity,
                    Json(event.details),
                ),
            )
            row = cursor.fetchone()
            event_ids.append(row[0])

    return tuple(event_ids)
