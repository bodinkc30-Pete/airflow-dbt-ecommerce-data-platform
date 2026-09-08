from pathlib import Path

import pandas as pd

from ecommerce_pipeline.ingestion.extraction_adapters import (
    extract_source_file,
)
from ecommerce_pipeline.ingestion.schema_drift import (
    classify_schema_drift,
)
from ecommerce_pipeline.ingestion.schema_validation import (
    validate_schema,
)


def _core_columns(total: int) -> list[str]:
    columns = [
        "Influencer",
        "Follower",
        "Engangement Rate%",
        "BUDGET",
    ]
    while len(columns) < total:
        columns.append(f"column_{len(columns) + 1}")
    return columns


def test_blank_identity_row_with_other_values_is_retained(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "influencer_data.csv"
    columns = _core_columns(12)
    rows = [
        ["Synthetic Creator", "1000", "5%", "1500"] + [""] * 8,
        ["", "2000", "7%", "2000"] + [""] * 8,
        [""] * 12,
    ]
    pd.DataFrame(rows, columns=columns).to_csv(file_path, index=False)

    result = extract_source_file("influencer_roster", file_path)

    assert result.row_count == 2
    assert result.dataframe.iloc[1]["Influencer"] == ""
    assert result.dataframe.iloc[1]["Follower"] == "2000"


def test_influencer_schema_requires_all_verified_core_headers() -> None:
    result = validate_schema(
        source_name="influencer_roster",
        observed_columns=_core_columns(12),
    )
    assert result.status == "VALID"
    assert result.missing_required_columns == ()


def test_missing_influencer_identity_header_is_invalid() -> None:
    columns = _core_columns(12)
    columns[0] = "Creator Alias"
    result = validate_schema(
        source_name="influencer_roster",
        observed_columns=columns,
    )
    assert result.status == "INVALID"
    assert result.missing_required_columns == ("influencer_name",)


def test_influencer_column_count_drift_is_auditable() -> None:
    result = validate_schema(
        source_name="influencer_roster",
        observed_columns=_core_columns(11),
    )
    events = classify_schema_drift(result)
    count_event = next(
        event
        for event in events
        if event.details["validation_issue_code"]
        == "COLUMN_COUNT_MISMATCH"
    )
    assert count_event.expected_value == "12"
    assert count_event.observed_value == "11"
    assert count_event.severity == "error"


def test_unverified_header_alias_does_not_false_pass_schema() -> None:
    columns = _core_columns(12)
    columns[2] = "Engagement Rate%"
    result = validate_schema(
        source_name="influencer_roster",
        observed_columns=columns,
    )
    assert result.status == "INVALID"
    assert result.missing_required_columns == ("engagement_rate",)
