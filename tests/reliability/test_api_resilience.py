"""Unit tests for the API resilience lab.

Runs entirely against a synthetic localhost server (see ``fake_api_server.py``);
no external network access is required. Timeouts and backoffs are kept tiny so
the whole file finishes in a few seconds.
"""

from __future__ import annotations

import time
from unittest import mock

import pytest
from fake_api_server import FakeApiServer

from ecommerce_pipeline.reliability.api_resilience import (
    CallStatus,
    CircuitBreakerState,
    ResilientApiClient,
)


@pytest.fixture()
def server():
    """Provide a fresh fake API server per test."""
    with FakeApiServer() as fake:
        yield fake


def _client(server: FakeApiServer, **overrides: object) -> ResilientApiClient:
    """Build a client with fast, deterministic defaults for tests."""
    config = {
        "timeout_seconds": 0.3,
        "max_attempts": 3,
        "backoff_base_seconds": 0.01,
        "backoff_multiplier": 2.0,
        "jitter": False,
        "retry_budget_per_window": 10,
        "retry_budget_window_seconds": 30.0,
        "circuit_failure_threshold": 3,
        "circuit_reset_seconds": 30.0,
    }
    config.update(overrides)
    return ResilientApiClient(server.url, **config)  # type: ignore[arg-type]


def test_success_on_first_attempt(server: FakeApiServer) -> None:
    client = _client(server)
    result = client.request("POST", "/ok", body={"order_id": 1})

    assert result.status is CallStatus.SUCCESS
    assert result.attempts == 1
    assert result.http_status == 200
    assert result.error is None
    assert result.latency_ms >= 0.0
    assert server.state.request_count("/ok") == 1
    # The idempotency key must be sent on the wire.
    assert server.state.idempotency_keys_for("/ok") == [result.idempotency_key]


def test_flaky_server_recovers_after_retries(server: FakeApiServer) -> None:
    client = _client(server, max_attempts=3)
    with mock.patch.object(client, "compute_backoff", wraps=client.compute_backoff) as backoff:
        result = client.request("POST", "/flaky?fail_times=2")

    assert result.status is CallStatus.SUCCESS
    assert result.attempts == 3
    assert result.http_status == 200
    # Backoff was computed once per retry (attempts 1 and 2 failed).
    assert backoff.call_count == 2
    assert [call.args[0] for call in backoff.call_args_list] == [1, 2]
    # All attempts carried the same idempotency key.
    keys = server.state.idempotency_keys_for("/flaky")
    assert len(keys) == 3 and len(set(keys)) == 1


def test_persistent_500_stops_at_max_attempts(server: FakeApiServer) -> None:
    client = _client(server, max_attempts=4)
    result = client.request("POST", "/server-error")

    assert result.status is CallStatus.FAILED
    assert result.attempts == 4
    assert result.http_status == 500
    assert result.error is not None and "500" in result.error
    assert server.state.request_count("/server-error") == 4


def test_429_is_retried_per_policy(server: FakeApiServer) -> None:
    client = _client(server, max_attempts=3)
    result = client.request("GET", "/rate-limited")

    assert result.status is CallStatus.FAILED
    assert result.attempts == 3
    assert result.http_status == 429
    assert server.state.request_count("/rate-limited") == 3


def test_404_is_not_retried(server: FakeApiServer) -> None:
    client = _client(server, max_attempts=5)
    result = client.request("GET", "/no-such-resource")

    assert result.status is CallStatus.FAILED
    assert result.attempts == 1
    assert result.http_status == 404
    assert result.error is not None and "non-retryable" in result.error
    assert server.state.request_count("/no-such-resource") == 1


def test_timeout_counts_as_failure_and_is_retried(server: FakeApiServer) -> None:
    client = _client(server, timeout_seconds=0.3, max_attempts=2)
    result = client.request("GET", "/timeout")

    assert result.status is CallStatus.FAILED
    assert result.attempts == 2
    assert result.http_status is None
    assert result.error is not None
    # Both attempts reached the server even though no response was read.
    assert server.state.request_count("/timeout") == 2


def test_retry_budget_exhaustion_fails_fast(server: FakeApiServer) -> None:
    client = _client(
        server,
        max_attempts=5,
        retry_budget_per_window=1,
        retry_budget_window_seconds=60.0,
    )
    result = client.request("POST", "/server-error")

    assert result.status is CallStatus.FAILED
    # Initial attempt + the single budgeted retry; remaining attempts skipped.
    assert result.attempts == 2
    assert result.error is not None and "retry budget exhausted" in result.error
    assert server.state.request_count("/server-error") == 2


def test_circuit_breaker_opens_rejects_then_recovers(server: FakeApiServer) -> None:
    client = _client(
        server,
        max_attempts=1,
        circuit_failure_threshold=2,
        circuit_reset_seconds=0.3,
    )

    first = client.request("POST", "/server-error")
    second = client.request("POST", "/server-error")
    assert first.status is CallStatus.FAILED
    assert second.status is CallStatus.FAILED
    assert client.circuit_state is CircuitBreakerState.OPEN
    assert server.state.request_count("/server-error") == 2

    # While open, calls are rejected without touching the network.
    rejected = client.request("POST", "/ok")
    assert rejected.status is CallStatus.REJECTED_BY_BREAKER
    assert rejected.attempts == 0
    assert rejected.error is not None and "circuit breaker is open" in rejected.error
    assert server.state.request_count("/ok") == 0

    # After the reset window the breaker half-opens; a success closes it.
    time.sleep(0.4)
    recovered = client.request("POST", "/ok")
    assert recovered.status is CallStatus.SUCCESS
    assert recovered.attempts == 1
    assert client.circuit_state is CircuitBreakerState.CLOSED
    assert server.state.request_count("/ok") == 1


def test_idempotent_retry_does_not_duplicate_invoice(server: FakeApiServer) -> None:
    client = _client(server, timeout_seconds=0.3, max_attempts=1)
    key = ResilientApiClient.generate_idempotency_key()

    # The response is "lost" both times (server answers slower than the
    # timeout), so the client sees two failures and would normally retry
    # blindly. Because both calls carry the same Idempotency-Key, the server
    # creates exactly one invoice.
    first = client.request("POST", "/lost-response", idempotency_key=key)
    second = client.request("POST", "/lost-response", idempotency_key=key)

    assert first.status is CallStatus.FAILED
    assert second.status is CallStatus.FAILED
    assert first.idempotency_key == second.idempotency_key == key
    assert server.state.request_count("/lost-response") == 2
    assert len(server.state.invoices) == 1
    assert list(server.state.invoices) == [key]


def test_generate_idempotency_key_is_unique() -> None:
    keys = {ResilientApiClient.generate_idempotency_key() for _ in range(100)}
    assert len(keys) == 100
    assert all(key.startswith("idem-") for key in keys)


def test_compute_backoff_grows_exponentially_without_jitter(server: FakeApiServer) -> None:
    client = _client(server, backoff_base_seconds=0.5, backoff_multiplier=3.0, jitter=False)
    assert client.compute_backoff(1) == pytest.approx(0.5)
    assert client.compute_backoff(2) == pytest.approx(1.5)
    assert client.compute_backoff(3) == pytest.approx(4.5)


def test_compute_backoff_with_jitter_stays_within_bounds(server: FakeApiServer) -> None:
    client = _client(server, backoff_base_seconds=0.5, backoff_multiplier=3.0, jitter=True)
    caps = {1: 0.5, 2: 1.5, 3: 4.5}
    for attempt, cap in caps.items():
        samples = [client.compute_backoff(attempt) for _ in range(50)]
        assert all(0.0 <= value <= cap for value in samples)
    # Jitter should actually spread values, not return a constant.
    assert len({round(client.compute_backoff(3), 6) for _ in range(20)}) > 1


def test_invalid_config_is_rejected(server: FakeApiServer) -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        _client(server, max_attempts=0)
    with pytest.raises(ValueError, match="timeout_seconds"):
        _client(server, timeout_seconds=0)
