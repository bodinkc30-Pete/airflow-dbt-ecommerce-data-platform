from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from ecommerce_pipeline.ingestion.file_registry import (
    FileRegistrationResult,
)

IdempotencyAction = Literal[
    "process",
    "skip_duplicate",
    "block",
]


@dataclass(frozen=True)
class IdempotencyDecision:
    action: IdempotencyAction
    reason: str

    @property
    def should_process(self) -> bool:
        return self.action == "process"


def decide_file_processing(
    registration: FileRegistrationResult,
    *,
    current_ingestion_run_id: int,
    stale_processing_ttl: timedelta | None = None,
) -> IdempotencyDecision:
    """
    Decide whether a registered file is eligible for processing.

    New files are processable. Successfully completed duplicates are
    skipped. Failed duplicates are retryable within the same ingestion
    run. A file stuck in ``processing`` (e.g. worker killed mid-load by
    SIGKILL, pod eviction, or a hard task timeout) is automatically
    retried once its ``processing_started_at`` exceeds
    ``stale_processing_ttl`` — without this recovery path a stale
    record would block every subsequent run permanently. Other
    duplicate lifecycle states are blocked until an explicit
    reprocessing policy exists.
    """

    if not registration.is_duplicate:
        return IdempotencyDecision(
            action="process",
            reason="new_file",
        )

    if registration.status in {
        "success",
        "skipped_duplicate",
    }:
        return IdempotencyDecision(
            action="skip_duplicate",
            reason="already_processed",
        )

    if registration.status == "processing" and _is_stale_processing(
        registration,
        stale_processing_ttl,
    ):
        return IdempotencyDecision(
            action="process",
            reason="retry_stale_processing",
        )

    if registration.status == "failed":
        if registration.ingestion_run_id != current_ingestion_run_id:
            return IdempotencyDecision(
                action="block",
                reason=(
                    "cross_run_retry_requires_explicit_reprocessing_policy"
                ),
            )

        return IdempotencyDecision(
            action="process",
            reason="retry_failed_file",
        )

    return IdempotencyDecision(
        action="block",
        reason=(
            "duplicate_requires_explicit_reprocessing_policy:"
            f"{registration.status}"
        ),
    )


def _is_stale_processing(
    registration: FileRegistrationResult,
    stale_processing_ttl: timedelta | None,
) -> bool:
    """Return True when a ``processing`` record exceeded its TTL."""
    if stale_processing_ttl is None:
        return False

    started_at = registration.processing_started_at

    if started_at is None:
        return False

    if started_at.tzinfo is None:
        now = datetime.now()
    else:
        now = datetime.now(UTC)

    return now - started_at > stale_processing_ttl
