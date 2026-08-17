import os
from datetime import date
from uuid import uuid4

import pytest

from ecommerce_pipeline.ingestion.file_registry import connect_postgres
from ecommerce_pipeline.ingestion.incremental_state import (
    get_watermark_state,
    upsert_watermark_state,
)
from ecommerce_pipeline.ingestion.late_arriving import (
    decide_metric_date_processing,
)
from ecommerce_pipeline.ingestion.schema_contracts import (
    SCHEMA_CONTRACTS,
    RequiredColumn,
    SchemaContract,
)
from ecommerce_pipeline.ingestion.source_registry import (
    SOURCE_REGISTRY,
    SourceConfig,
)
from ecommerce_pipeline.ingestion.transaction import transaction_scope


@pytest.fixture
def postgres_connection():
    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )
    connection.autocommit = False

    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()


def _delete_test_watermark(
    connection,
    *,
    source_name: str,
) -> None:
    connection.rollback()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM audit.source_watermarks
            WHERE source_name = %s;
            """,
            (source_name,),
        )

    connection.commit()


def test_late_arriving_backfill_does_not_rewind_watermark(
    postgres_connection,
    monkeypatch,
) -> None:
    source_name = f"pytest_late_arriving_{uuid4().hex}"

    monkeypatch.setitem(
        SOURCE_REGISTRY,
        source_name,
        SourceConfig(
            source_id=f"SRC_{uuid4().hex}",
            source_name=source_name,
            domain="Pytest",
            file_pattern="*.csv",
            file_format="csv",
            target_table="raw.shop_daily",
            contract_path=(
                "docs/source_contracts/"
                "pytest_late_arriving_source_contract.md"
            ),
            load_strategy="incremental",
            expected_grain="one row per metric date",
            business_key=("metric_date",),
            supports_multiple_files=True,
            supports_late_arriving_data=True,
        ),
    )

    monkeypatch.setitem(
        SCHEMA_CONTRACTS,
        source_name,
        SchemaContract(
            source_name=source_name,
            expected_column_count=1,
            header_strategy="flat",
            drift_policy="strict",
            required_columns=(
                RequiredColumn(
                    canonical_name="metric_date",
                    accepted_source_names=(
                        "Date",
                        "metric_date",
                    ),
                ),
            ),
        ),
    )

    try:
        with transaction_scope(postgres_connection):
            initial_state = upsert_watermark_state(
                postgres_connection,
                source_name=source_name,
                watermark_type="date",
                watermark_value="2026-08-10",
                last_successful_run_id=None,
                last_successful_file_id=None,
            )

        assert initial_state.watermark_value == "2026-08-10"

        historical_decision = decide_metric_date_processing(
            source_name=source_name,
            candidate_date=date(2026, 8, 5),
            current_watermark=date(2026, 8, 10),
            processing_mode="backfill",
        )

        assert historical_decision.should_process is True
        assert historical_decision.should_advance_watermark is False
        assert historical_decision.is_late_arriving is True
        assert historical_decision.reason == "historical_backfill"

        state_after_historical_backfill = get_watermark_state(
            postgres_connection,
            source_name=source_name,
        )

        assert state_after_historical_backfill == initial_state
        assert (
            state_after_historical_backfill.watermark_value
            == "2026-08-10"
        )

        newer_decision = decide_metric_date_processing(
            source_name=source_name,
            candidate_date=date(2026, 8, 12),
            current_watermark=date(2026, 8, 10),
        )

        assert newer_decision.should_process is True
        assert newer_decision.should_advance_watermark is True
        assert newer_decision.reason == "newer_metric_date"

        with transaction_scope(postgres_connection):
            advanced_state = upsert_watermark_state(
                postgres_connection,
                source_name=source_name,
                watermark_type="date",
                watermark_value="2026-08-12",
                last_successful_run_id=None,
                last_successful_file_id=None,
            )

        persisted_advanced_state = get_watermark_state(
            postgres_connection,
            source_name=source_name,
        )

        assert persisted_advanced_state == advanced_state
        assert persisted_advanced_state.watermark_value == "2026-08-12"
    finally:
        _delete_test_watermark(
            postgres_connection,
            source_name=source_name,
        )
