"""Synthetic HTTP API server used by the API resilience lab tests.

Runs a ``ThreadingHTTPServer`` on a random localhost port (port 0) and simulates
production failure modes through paths:

- ``/ok``             -> 200 ``{"status": "created"}``; records the Idempotency-Key.
- ``/timeout``        -> sleeps far beyond any client timeout, then 200.
- ``/rate-limited``   -> always 429.
- ``/server-error``   -> always 500.
- ``/flaky?fail_times=N`` -> 500 for the first N requests carrying a given
  Idempotency-Key, then 200 (retry-then-succeed scenario).
- ``/lost-response``  -> records an invoice keyed by Idempotency-Key (an already
  seen key is NOT duplicated, i.e. the server is idempotent), then answers
  slower than the client timeout (simulates a lost response).

The helper exposes the observed state (request counts, idempotency keys,
created invoices) so tests can assert both client- and server-side behavior.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from urllib.parse import parse_qs, urlparse

SLOW_RESPONSE_SECONDS = 30.0
"""Delay used by /timeout and /lost-response; must exceed any client timeout."""


class FakeApiState:
    """Thread-safe record of everything the fake server observed."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._request_counts: dict[str, int] = {}
        self._idempotency_keys: dict[str, list[str | None]] = {}
        self._invoices: dict[str, dict[str, str]] = {}
        self._flaky_attempts: dict[str, int] = {}

    def record_request(self, path: str, idempotency_key: str | None) -> None:
        """Record an incoming request and its idempotency key."""
        with self._lock:
            self._request_counts[path] = self._request_counts.get(path, 0) + 1
            self._idempotency_keys.setdefault(path, []).append(idempotency_key)

    def flaky_attempt_number(self, idempotency_key: str | None) -> int:
        """Return the 1-based attempt number for this key on /flaky."""
        with self._lock:
            seen = self._flaky_attempts.get(idempotency_key or "", 0) + 1
            self._flaky_attempts[idempotency_key or ""] = seen
            return seen

    def create_invoice(self, idempotency_key: str | None) -> tuple[str, bool]:
        """Create an invoice unless one already exists for this key.

        Returns ``(invoice_id, created)`` where ``created`` is False when the
        key was already processed (idempotent replay).
        """
        key = idempotency_key or "<missing>"
        with self._lock:
            if key in self._invoices:
                return self._invoices[key]["invoice_id"], False
            invoice_id = f"inv-{len(self._invoices) + 1:04d}"
            self._invoices[key] = {"invoice_id": invoice_id, "idempotency_key": key}
            return invoice_id, True

    # ------------------------------ accessors ------------------------- #

    def request_count(self, path: str) -> int:
        """Number of requests received for ``path``."""
        with self._lock:
            return self._request_counts.get(path, 0)

    def idempotency_keys_for(self, path: str) -> list[str | None]:
        """Idempotency keys observed for ``path``, in arrival order."""
        with self._lock:
            return list(self._idempotency_keys.get(path, []))

    @property
    def invoices(self) -> dict[str, dict[str, str]]:
        """Invoices created so far, keyed by idempotency key."""
        with self._lock:
            return dict(self._invoices)

    def reset(self) -> None:
        """Clear all recorded state."""
        with self._lock:
            self._request_counts.clear()
            self._idempotency_keys.clear()
            self._invoices.clear()
            self._flaky_attempts.clear()


class _FakeApiHandler(BaseHTTPRequestHandler):
    """Request handler dispatching on the synthetic scenario paths."""

    server: _FakeApiHttpServer

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
        self._handle()

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
        self._handle()

    def log_message(self, format: str, *args: object) -> None:
        """Silence default stderr logging during tests."""

    def _handle(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        content_length = int(self.headers.get("Content-Length") or 0)
        if content_length:
            self.rfile.read(content_length)
        idempotency_key = self.headers.get("Idempotency-Key")
        state = self.server.state
        state.record_request(path, idempotency_key)

        if path == "/ok":
            self._respond(200, {"status": "created"})
        elif path == "/timeout":
            time.sleep(SLOW_RESPONSE_SECONDS)
            self._respond(200, {"status": "too late"})
        elif path == "/rate-limited":
            self._respond(429, {"error": "rate limited"})
        elif path == "/server-error":
            self._respond(500, {"error": "internal server error"})
        elif path == "/flaky":
            fail_times = int(params.get("fail_times", ["0"])[0])
            attempt = state.flaky_attempt_number(idempotency_key)
            if attempt <= fail_times:
                self._respond(500, {"error": f"flaky failure {attempt}/{fail_times}"})
            else:
                self._respond(200, {"status": "created", "attempt": attempt})
        elif path == "/lost-response":
            invoice_id, created = state.create_invoice(idempotency_key)
            # Simulate a lost response: work is done, but the reply arrives
            # only after the client has already given up on the attempt.
            time.sleep(SLOW_RESPONSE_SECONDS)
            self._respond(200, {"invoice_id": invoice_id, "created": created})
        else:
            self._respond(404, {"error": f"unknown path: {path}"})

    def _respond(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # The client timed out and closed the socket; nothing to do.
            pass


class _FakeApiHttpServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, state: FakeApiState) -> None:
        super().__init__(("127.0.0.1", 0), _FakeApiHandler)
        self.state = state


class FakeApiServer:
    """Context-managed fake API server bound to a random localhost port."""

    def __init__(self) -> None:
        self.state = FakeApiState()
        self._server = _FakeApiHttpServer(self.state)
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="fake-api-server", daemon=True
        )

    @property
    def url(self) -> str:
        """Base URL of the running server, e.g. ``http://127.0.0.1:54321``."""
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> FakeApiServer:
        """Start serving in a background thread."""
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stop serving and release the port."""
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __enter__(self) -> FakeApiServer:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()
