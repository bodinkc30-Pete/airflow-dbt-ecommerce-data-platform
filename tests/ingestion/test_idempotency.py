import pytest

from ecommerce_pipeline.ingestion.file_registry import (
    FileRegistrationResult,
)
from ecommerce_pipeline.ingestion.idempotency import (
    decide_file_processing,
)


def _registration(
    *,
    is_duplicate: bool,
    status: str,
) -> FileRegistrationResult:
    return FileRegistrationResult(
        ingestion_file_id=100,
        ingestion_run_id=11,
        source_name="orders",
        file_hash_sha256="a" * 64,
        status=status,
        is_duplicate=is_duplicate,
    )


def test_new_file_is_processable() -> None:
    decision = decide_file_processing(
        _registration(
            is_duplicate=False,
            status="discovered",
        ),
        current_ingestion_run_id=11,
    )

    assert decision.action == "process"
    assert decision.reason == "new_file"
    assert decision.should_process is True


@pytest.mark.parametrize(
    "status",
    [
        "success",
        "skipped_duplicate",
    ],
)
def test_completed_duplicate_is_skipped(
    status: str,
) -> None:
    decision = decide_file_processing(
        _registration(
            is_duplicate=True,
            status=status,
        ),
        current_ingestion_run_id=11,
    )

    assert decision.action == "skip_duplicate"
    assert decision.reason == "already_processed"
    assert decision.should_process is False


def test_failed_duplicate_is_retryable() -> None:
    decision = decide_file_processing(
        _registration(
            is_duplicate=True,
            status="failed",
        ),
        current_ingestion_run_id=11,
    )

    assert decision.action == "process"
    assert decision.reason == "retry_failed_file"
    assert decision.should_process is True


@pytest.mark.parametrize(
    "status",
    [
        "discovered",
        "processing",
        "rejected",
    ],
)
def test_duplicate_without_reprocessing_policy_is_blocked(
    status: str,
) -> None:
    decision = decide_file_processing(
        _registration(
            is_duplicate=True,
            status=status,
        ),
        current_ingestion_run_id=11,
    )

    assert decision.action == "block"
    assert decision.reason == (
        "duplicate_requires_explicit_reprocessing_policy:"
        f"{status}"
    )
    assert decision.should_process is False


def test_failed_duplicate_from_different_run_is_blocked() -> None:
    registration = FileRegistrationResult(
        ingestion_file_id=100,
        ingestion_run_id=11,
        source_name="orders",
        file_hash_sha256="a" * 64,
        status="failed",
        is_duplicate=True,
    )

    decision = decide_file_processing(
        registration,
        current_ingestion_run_id=22,
    )

    assert decision.action == "block"
    assert decision.reason == (
        "cross_run_retry_requires_explicit_reprocessing_policy"
    )
    assert decision.should_process is False
