from dataclasses import dataclass
from datetime import date
from typing import Literal

from ecommerce_pipeline.ingestion.schema_contracts import (
    get_schema_contract,
)
from ecommerce_pipeline.ingestion.source_registry import (
    get_source_config,
)

ProcessingMode = Literal[
    "incremental",
    "backfill",
]

LateArrivingAction = Literal[
    "process",
    "block",
]

WatermarkAction = Literal[
    "advance",
    "keep",
]


@dataclass(frozen=True)
class LateArrivingDecision:
    action: LateArrivingAction
    watermark_action: WatermarkAction
    reason: str
    is_late_arriving: bool
    is_backfill: bool

    @property
    def should_process(self) -> bool:
        return self.action == "process"

    @property
    def should_advance_watermark(self) -> bool:
        return self.watermark_action == "advance"


def _has_verified_metric_date_contract(
    source_name: str,
) -> bool:
    contract = get_schema_contract(source_name)

    return any(
        column.canonical_name == "metric_date"
        for column in contract.required_columns
    )


def decide_metric_date_processing(
    *,
    source_name: str,
    candidate_date: date,
    current_watermark: date | None,
    processing_mode: ProcessingMode = "incremental",
) -> LateArrivingDecision:
    """
    Decide how a normalized metric date interacts with the current watermark.

    This function intentionally accepts ``datetime.date`` values only.
    Parsing source text belongs to schema/normalization logic, not to the
    late-arriving policy.

    A source may use this generic policy only when its schema contract has a
    verified canonical ``metric_date`` field and its load strategy is
    incremental.
    """

    source_config = get_source_config(source_name)

    if source_config.load_strategy != "incremental":
        return LateArrivingDecision(
            action="block",
            watermark_action="keep",
            reason="source_is_not_incremental",
            is_late_arriving=False,
            is_backfill=processing_mode == "backfill",
        )

    if not _has_verified_metric_date_contract(source_name):
        return LateArrivingDecision(
            action="block",
            watermark_action="keep",
            reason="metric_date_contract_not_verified",
            is_late_arriving=False,
            is_backfill=processing_mode == "backfill",
        )

    if current_watermark is None:
        return LateArrivingDecision(
            action="process",
            watermark_action="advance",
            reason=(
                "initial_backfill_watermark"
                if processing_mode == "backfill"
                else "initial_incremental_watermark"
            ),
            is_late_arriving=False,
            is_backfill=processing_mode == "backfill",
        )

    if candidate_date > current_watermark:
        return LateArrivingDecision(
            action="process",
            watermark_action="advance",
            reason=(
                "backfill_advances_watermark"
                if processing_mode == "backfill"
                else "newer_metric_date"
            ),
            is_late_arriving=False,
            is_backfill=processing_mode == "backfill",
        )

    if candidate_date == current_watermark:
        return LateArrivingDecision(
            action="process",
            watermark_action="keep",
            reason=(
                "backfill_at_current_watermark"
                if processing_mode == "backfill"
                else "same_metric_date"
            ),
            is_late_arriving=False,
            is_backfill=processing_mode == "backfill",
        )

    if not source_config.supports_late_arriving_data:
        return LateArrivingDecision(
            action="block",
            watermark_action="keep",
            reason="late_arriving_data_not_supported",
            is_late_arriving=True,
            is_backfill=processing_mode == "backfill",
        )

    return LateArrivingDecision(
        action="process",
        watermark_action="keep",
        reason=(
            "historical_backfill"
            if processing_mode == "backfill"
            else "late_arriving_correction"
        ),
        is_late_arriving=True,
        is_backfill=processing_mode == "backfill",
    )
