"""Resilient HTTP client lab for external API integrations.

This module is a self-contained lab (not wired into any production pipeline) that
demonstrates production-grade integration patterns against a synthetic HTTP API:

- per-attempt timeouts,
- retries with exponential backoff and optional jitter,
- a sliding-window retry budget (fail fast instead of amplifying an outage),
- a circuit breaker (closed / open / half-open),
- per-logical-request idempotency keys so retries are safe to replay.

The client never raises: every call returns a :class:`CallResult`.
Only the Python standard library (``urllib``) is used.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
import uuid
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

RETRYABLE_HTTP_STATUS = 429
"""HTTP status that signals transient rate limiting and is safe to retry."""


class CallStatus(StrEnum):
    """Terminal status of a logical API call."""

    SUCCESS = "success"
    FAILED = "failed"
    REJECTED_BY_BREAKER = "rejected_by_breaker"


class CircuitBreakerState(StrEnum):
    """State machine of the circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class CallResult:
    """Outcome of one logical API call (including all retry attempts)."""

    status: CallStatus
    attempts: int
    latency_ms: float
    http_status: int | None
    error: str | None
    idempotency_key: str


class ResilientApiClient:
    """HTTP client with timeout, retry, retry budget, circuit breaker, idempotency.

    Args:
        base_url: Base URL of the target API, e.g. ``http://127.0.0.1:8080``.
        timeout_seconds: Per-attempt socket timeout.
        max_attempts: Maximum total attempts (initial try + retries) per call.
        backoff_base_seconds: Base delay for exponential backoff.
        backoff_multiplier: Multiplier applied per failed attempt.
        jitter: When True, the actual sleep is ``uniform(0, backoff)`` to decorrelate
            retries across clients.
        retry_budget_per_window: Maximum number of retries allowed inside
            ``retry_budget_window_seconds``. Exceeding it fails the call fast.
        retry_budget_window_seconds: Sliding window for the retry budget.
        circuit_failure_threshold: Consecutive failed calls that open the breaker.
        circuit_reset_seconds: How long the breaker stays open before a half-open
            probe is allowed.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 2.0,
        max_attempts: int = 3,
        backoff_base_seconds: float = 0.1,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        retry_budget_per_window: int = 5,
        retry_budget_window_seconds: float = 10.0,
        circuit_failure_threshold: int = 3,
        circuit_reset_seconds: float = 30.0,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.retry_budget_per_window = retry_budget_per_window
        self.retry_budget_window_seconds = retry_budget_window_seconds
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_reset_seconds = circuit_reset_seconds

        self._retry_timestamps: deque[float] = deque()
        self._consecutive_failures = 0
        self._breaker_state = CircuitBreakerState.CLOSED
        self._breaker_opened_at: float | None = None

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    @property
    def circuit_state(self) -> CircuitBreakerState:
        """Current circuit breaker state."""
        return self._breaker_state

    @staticmethod
    def generate_idempotency_key() -> str:
        """Generate a unique idempotency key for one logical request.

        The same key is reused across all retries of that request; a new key is
        generated for each new logical request.
        """
        return f"idem-{uuid.uuid4().hex}"

    def compute_backoff(self, attempt: int) -> float:
        """Compute the delay (seconds) before retrying after ``attempt`` failed.

        ``attempt`` is 1-based (the attempt that just failed). Without jitter the
        delay grows exponentially as ``base * multiplier ** (attempt - 1)``; with
        jitter the returned value is uniform in ``[0, delay]``.
        """
        delay = self.backoff_base_seconds * (self.backoff_multiplier ** max(0, attempt - 1))
        if self.jitter:
            return random.uniform(0.0, delay)
        return delay

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> CallResult:
        """Execute one logical HTTP call with retries, budget and breaker.

        Never raises; all outcomes (including breaker rejections) are reported
        through the returned :class:`CallResult`.
        """
        started = time.monotonic()
        key = idempotency_key or self.generate_idempotency_key()

        def _elapsed_ms() -> float:
            return (time.monotonic() - started) * 1000.0

        breaker_error = self._check_breaker()
        if breaker_error is not None:
            return CallResult(
                status=CallStatus.REJECTED_BY_BREAKER,
                attempts=0,
                latency_ms=_elapsed_ms(),
                http_status=None,
                error=breaker_error,
                idempotency_key=key,
            )

        attempts = 0
        last_http_status: int | None = None
        last_error: str | None = None

        try:
            while attempts < self.max_attempts:
                if attempts > 0:
                    budget_error = self._consume_retry_budget()
                    if budget_error is not None:
                        self._record_failure()
                        return CallResult(
                            status=CallStatus.FAILED,
                            attempts=attempts,
                            latency_ms=_elapsed_ms(),
                            http_status=last_http_status,
                            error=budget_error,
                            idempotency_key=key,
                        )
                    time.sleep(self.compute_backoff(attempts))

                attempts += 1
                kind, http_status, error = self._single_attempt(method, path, body, headers, key)
                last_http_status = http_status
                last_error = error

                if kind == "success":
                    self._record_success()
                    return CallResult(
                        status=CallStatus.SUCCESS,
                        attempts=attempts,
                        latency_ms=_elapsed_ms(),
                        http_status=http_status,
                        error=None,
                        idempotency_key=key,
                    )
                if kind == "fatal":
                    # Non-retryable client error (e.g. HTTP 404): stop immediately.
                    break
                # kind == "retryable": loop again if attempts remain.

            self._record_failure()
            return CallResult(
                status=CallStatus.FAILED,
                attempts=attempts,
                latency_ms=_elapsed_ms(),
                http_status=last_http_status,
                error=last_error or "request failed",
                idempotency_key=key,
            )
        except Exception as exc:  # defensive: the client must never raise
            self._record_failure()
            return CallResult(
                status=CallStatus.FAILED,
                attempts=attempts,
                latency_ms=_elapsed_ms(),
                http_status=last_http_status,
                error=f"unexpected {type(exc).__name__}: {exc}",
                idempotency_key=key,
            )

    # ------------------------------------------------------------------ #
    # Internals                                                           #
    # ------------------------------------------------------------------ #

    def _single_attempt(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        headers: dict[str, str] | None,
        idempotency_key: str,
    ) -> tuple[str, int | None, str | None]:
        """Perform one HTTP attempt and classify the outcome.

        Returns ``(kind, http_status, error)`` where kind is one of
        ``"success"``, ``"retryable"`` or ``"fatal"``.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method.upper())
        request.add_header("Idempotency-Key", idempotency_key)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        for name, value in (headers or {}).items():
            request.add_header(name, value)

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response.read()
                return "success", int(response.status), None
        except urllib.error.HTTPError as exc:
            code = int(exc.code)
            if code == RETRYABLE_HTTP_STATUS or 500 <= code < 600:
                return "retryable", code, f"transient HTTP {code}"
            return "fatal", code, f"non-retryable HTTP {code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # Timeouts and connection errors are transient by definition.
            return "retryable", None, f"{type(exc).__name__}: {exc}"

    def _check_breaker(self) -> str | None:
        """Return a rejection reason if the breaker is open, else None.

        Transitions OPEN -> HALF_OPEN once the reset window has elapsed so the
        next call acts as a probe.
        """
        if self._breaker_state is not CircuitBreakerState.OPEN:
            return None
        opened_at = self._breaker_opened_at
        if opened_at is not None and time.monotonic() - opened_at >= self.circuit_reset_seconds:
            self._breaker_state = CircuitBreakerState.HALF_OPEN
            return None
        return (
            "circuit breaker is open: call rejected without sending a request "
            f"(retry after {self.circuit_reset_seconds}s reset window)"
        )

    def _record_success(self) -> None:
        """Reset failure counters and close the breaker after a success."""
        self._consecutive_failures = 0
        self._breaker_state = CircuitBreakerState.CLOSED
        self._breaker_opened_at = None

    def _record_failure(self) -> None:
        """Count a failed logical call and open the breaker at the threshold."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.circuit_failure_threshold:
            self._breaker_state = CircuitBreakerState.OPEN
            self._breaker_opened_at = time.monotonic()

    def _consume_retry_budget(self) -> str | None:
        """Consume one retry token from the sliding-window budget.

        Returns an error message when the budget is exhausted (fail fast),
        otherwise records the retry and returns None.
        """
        now = time.monotonic()
        window_start = now - self.retry_budget_window_seconds
        while self._retry_timestamps and self._retry_timestamps[0] < window_start:
            self._retry_timestamps.popleft()
        if len(self._retry_timestamps) >= self.retry_budget_per_window:
            return (
                f"retry budget exhausted: {len(self._retry_timestamps)} retries in the last "
                f"{self.retry_budget_window_seconds}s window (limit "
                f"{self.retry_budget_per_window}); failing fast to protect the downstream API"
            )
        self._retry_timestamps.append(now)
        return None
