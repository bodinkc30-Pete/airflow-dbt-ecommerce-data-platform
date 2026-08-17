from unittest.mock import Mock

import pytest

from ecommerce_pipeline.ingestion.transaction import transaction_scope


def test_transaction_scope_commits_on_success() -> None:
    connection = Mock()

    with transaction_scope(connection) as active_connection:
        assert active_connection is connection

    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()


def test_transaction_scope_rolls_back_on_failure() -> None:
    connection = Mock()

    with pytest.raises(
        RuntimeError,
        match="simulated failure",
    ):
        with transaction_scope(connection):
            raise RuntimeError("simulated failure")

    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()


def test_transaction_scope_reraises_original_exception() -> None:
    connection = Mock()
    error = ValueError("original error")

    with pytest.raises(ValueError) as exc_info:
        with transaction_scope(connection):
            raise error

    assert exc_info.value is error
    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()
