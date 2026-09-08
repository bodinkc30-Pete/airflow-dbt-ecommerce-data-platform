from unittest.mock import MagicMock

import pandas as pd

from ecommerce_pipeline.ingestion.data_quality import (
    evaluate_influencer_roster_quality,
    has_blocking_quality_failures,
    record_data_quality_results,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Influencer": ["Creator A", "Creator B"],
            "Follower": ["1000", "2000"],
            "Engangement Rate%": ["5%", "7.5%"],
            "BUDGET": ["1500", "2000"],
        }
    )


def test_valid_influencer_quality_has_no_blocking_failure() -> None:
    results = evaluate_influencer_roster_quality(_frame())
    assert results
    assert not has_blocking_quality_failures(results)
    assert all(result.status == "pass" for result in results)


def test_blank_identity_is_blocking_failure() -> None:
    frame = _frame()
    frame.loc[1, "Influencer"] = "  "
    results = evaluate_influencer_roster_quality(frame)
    identity = next(r for r in results if r.check_name == "influencer_identity_not_blank")
    assert identity.status == "fail"
    assert identity.rows_failed == 1
    assert has_blocking_quality_failures(results)


def test_normalized_duplicate_identity_is_warning() -> None:
    frame = _frame()
    frame.loc[1, "Influencer"] = " creator a "
    results = evaluate_influencer_roster_quality(frame)
    duplicate = next(r for r in results if r.check_name == "influencer_identity_duplicate")
    assert duplicate.status == "warning"
    assert duplicate.rows_failed == 2
    assert duplicate.details["duplicate_key_count"] == 1
    assert not has_blocking_quality_failures(results)


def test_bad_engagement_format_is_warning_not_blocking() -> None:
    frame = _frame()
    frame.loc[1, "Engangement Rate%"] = "not-a-rate"
    results = evaluate_influencer_roster_quality(frame)
    engagement = next(r for r in results if r.check_name == "engagement_rate_parseable_range")
    assert engagement.status == "warning"
    assert engagement.rows_failed == 1
    assert not has_blocking_quality_failures(results)


def test_negative_follower_and_budget_are_warnings() -> None:
    frame = _frame()
    frame.loc[0, "Follower"] = "-1"
    frame.loc[1, "BUDGET"] = "-5"
    results = evaluate_influencer_roster_quality(frame)
    follower = next(r for r in results if r.check_name == "follower_non_negative_numeric")
    budget = next(r for r in results if r.check_name == "budget_non_negative_numeric")
    assert follower.status == "warning" and follower.rows_failed == 1
    assert budget.status == "warning" and budget.rows_failed == 1


def test_record_data_quality_results_is_transaction_neutral() -> None:
    results = evaluate_influencer_roster_quality(_frame())
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = (501,)
    connection = MagicMock()
    connection.cursor.return_value = cursor
    ids = record_data_quality_results(
        connection,
        ingestion_run_id=11,
        ingestion_file_id=22,
        source_name="influencer_roster",
        results=results,
    )
    assert len(ids) == len(results)
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
