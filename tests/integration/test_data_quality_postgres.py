import os
from pathlib import Path

import pandas as pd
import pytest

from ecommerce_pipeline.ingestion.data_quality import (
    evaluate_influencer_roster_quality,
    record_data_quality_results,
)
from ecommerce_pipeline.ingestion.file_registry import (
    build_file_metadata,
    connect_postgres,
    register_file,
)


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


def _create_run(connection) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audit.ingestion_runs (pipeline_name, run_type, status)
            VALUES ('pytest_data_quality', 'test', 'running')
            RETURNING ingestion_run_id;
            """
        )
        return cursor.fetchone()[0]


def test_influencer_quality_results_persist_to_postgres(
    postgres_connection, tmp_path: Path
) -> None:
    source_file = tmp_path / "influencer_data.csv"
    source_file.write_text("synthetic-quality-test", encoding="utf-8")
    run_id = _create_run(postgres_connection)
    metadata = build_file_metadata(source_name="influencer_roster", file_path=source_file)
    registered = register_file(
        connection=postgres_connection,
        ingestion_run_id=run_id,
        metadata=metadata,
    )
    frame = pd.DataFrame(
        {
            "Influencer": ["Creator A", " creator a "],
            "Follower": ["1000", "2000"],
            "Engangement Rate%": ["5%", "invalid"],
            "BUDGET": ["1500", "2000"],
        }
    )
    results = evaluate_influencer_roster_quality(frame)
    result_ids = record_data_quality_results(
        postgres_connection,
        ingestion_run_id=run_id,
        ingestion_file_id=registered.ingestion_file_id,
        source_name="influencer_roster",
        results=results,
    )
    assert len(result_ids) == 5
    with postgres_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT check_name, status, rows_failed, details
            FROM audit.data_quality_results
            WHERE ingestion_file_id = %s
            ORDER BY check_name;
            """,
            (registered.ingestion_file_id,),
        )
        rows = cursor.fetchall()
    by_name = {row[0]: row[1:] for row in rows}
    assert by_name["influencer_identity_not_blank"][:2] == ("pass", 0)
    assert by_name["influencer_identity_duplicate"][:2] == ("warning", 2)
    assert by_name["influencer_identity_duplicate"][2]["duplicate_key_count"] == 1
    assert by_name["engagement_rate_parseable_range"][:2] == ("warning", 1)
