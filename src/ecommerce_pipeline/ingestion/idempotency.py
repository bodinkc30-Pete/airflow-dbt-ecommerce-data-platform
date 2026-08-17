from dataclasses import dataclass
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
) -> IdempotencyDecision:
    """
    Decide whether a registered file is eligible for processing.

    New files are processable. Successfully completed duplicates are
    skipped. Failed duplicates are retryable within the same ingestion
    run. Other duplicate lifecycle states are blocked until an explicit
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

    if registration.status == "failed":
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
