from datetime import date

from ecommerce_pipeline.ingestion.late_arriving import (
    decide_metric_date_processing,
)


def test_initial_incremental_date_advances_watermark() -> None:
    decision = decide_metric_date_processing(
        source_name="shop_analytics",
        candidate_date=date(2026, 8, 1),
        current_watermark=None,
    )

    assert decision.should_process is True
    assert decision.should_advance_watermark is True
    assert decision.reason == "initial_incremental_watermark"
    assert decision.is_late_arriving is False
    assert decision.is_backfill is False


def test_newer_metric_date_advances_watermark() -> None:
    decision = decide_metric_date_processing(
        source_name="live_performance",
        candidate_date=date(2026, 8, 2),
        current_watermark=date(2026, 8, 1),
    )

    assert decision.should_process is True
    assert decision.should_advance_watermark is True
    assert decision.reason == "newer_metric_date"
    assert decision.is_late_arriving is False


def test_same_metric_date_processes_without_advancing_watermark() -> None:
    decision = decide_metric_date_processing(
        source_name="product_card_traffic",
        candidate_date=date(2026, 8, 1),
        current_watermark=date(2026, 8, 1),
    )

    assert decision.should_process is True
    assert decision.should_advance_watermark is False
    assert decision.reason == "same_metric_date"
    assert decision.is_late_arriving is False


def test_older_metric_date_is_late_arriving_and_keeps_watermark() -> None:
    decision = decide_metric_date_processing(
        source_name="shop_analytics",
        candidate_date=date(2026, 7, 31),
        current_watermark=date(2026, 8, 1),
    )

    assert decision.should_process is True
    assert decision.should_advance_watermark is False
    assert decision.reason == "late_arriving_correction"
    assert decision.is_late_arriving is True


def test_historical_backfill_processes_without_rewinding_watermark() -> None:
    decision = decide_metric_date_processing(
        source_name="live_performance",
        candidate_date=date(2026, 7, 1),
        current_watermark=date(2026, 8, 1),
        processing_mode="backfill",
    )

    assert decision.should_process is True
    assert decision.should_advance_watermark is False
    assert decision.reason == "historical_backfill"
    assert decision.is_late_arriving is True
    assert decision.is_backfill is True


def test_campaign_metric_date_policy_processes_after_contract_verified() -> None:
    decision = decide_metric_date_processing(
        source_name="campaign_overview",
        candidate_date=date(2026, 8, 1),
        current_watermark=date(2026, 7, 31),
    )

    assert decision.should_process is True
    assert decision.should_advance_watermark is True
    assert decision.reason == "newer_metric_date"
    assert decision.is_late_arriving is False


def test_snapshot_source_is_blocked_from_metric_date_policy() -> None:
    decision = decide_metric_date_processing(
        source_name="product_master",
        candidate_date=date(2026, 8, 1),
        current_watermark=date(2026, 7, 31),
        processing_mode="backfill",
    )

    assert decision.should_process is False
    assert decision.should_advance_watermark is False
    assert decision.reason == "source_is_not_incremental"
    assert decision.is_backfill is True
