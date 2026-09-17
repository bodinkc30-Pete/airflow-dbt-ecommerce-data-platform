"""Fake invoice API for transactional-outbox drills.

Runs a real HTTP server on a localhost thread that mimics an *idempotent*
external invoice service:

- ``POST /invoice`` requires an ``Idempotency-Key`` header. The first request
  with a given key creates one invoice; every retry with the same key returns
  the SAME invoice without creating a duplicate (idempotent consumer).
- ``POST /invoice?mode=fail_once`` makes the FIRST request for each new
  idempotency key fail with HTTP 500 (without creating an invoice); the retry
  succeeds. This simulates a transient network/service failure.

The server records every request (count + keys) so drills can assert exactly
how many deliveries happened and how many invoices were actually created.
"""

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class RecordedRequest:
    """One HTTP request observed by the fake API."""

    idempotency_key: str | None
    body: dict[str, Any]
    mode: str | None


@dataclass
class _ServerState:
    """Mutable state shared with the request handler (guarded by ``lock``)."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    invoices_by_key: dict[str, dict[str, Any]] = field(default_factory=dict)
    requests: list[RecordedRequest] = field(default_factory=list)
    failed_once_keys: set[str] = field(default_factory=set)
    next_invoice_number: int = 1


class FakeInvoiceApi:
    """Context-managed fake invoice API listening on a random localhost port."""

    def __init__(self) -> None:
        self._state = _ServerState()
        state = self._state

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 (http.server API)
                parsed = urlparse(self.path)
                if parsed.path != "/invoice":
                    self.send_error(404, "unknown endpoint")
                    return

                mode = parse_qs(parsed.query).get("mode", [None])[0]
                length = int(self.headers.get("Content-Length") or 0)
                raw_body = self.rfile.read(length) if length else b"{}"
                try:
                    body = json.loads(raw_body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self.send_error(400, "invalid JSON body")
                    return

                idempotency_key = self.headers.get("Idempotency-Key")
                with state.lock:
                    state.requests.append(
                        RecordedRequest(
                            idempotency_key=idempotency_key,
                            body=body,
                            mode=mode,
                        )
                    )
                    if not idempotency_key:
                        status, response = 400, {"error": "missing Idempotency-Key header"}
                    elif idempotency_key in state.invoices_by_key:
                        # Idempotent replay: return the original invoice.
                        status, response = 200, state.invoices_by_key[idempotency_key]
                    elif mode == "fail_once" and idempotency_key not in state.failed_once_keys:
                        state.failed_once_keys.add(idempotency_key)
                        status, response = 500, {"error": "simulated transient failure"}
                    else:
                        invoice = {
                            "invoice_id": f"INV-{state.next_invoice_number:05d}",
                            "idempotency_key": idempotency_key,
                            "event": body,
                        }
                        state.next_invoice_number += 1
                        state.invoices_by_key[idempotency_key] = invoice
                        status, response = 201, invoice

                payload = json.dumps(response).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: Any) -> None:
                # Keep drill output clean.
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        """Base URL of the running fake API, e.g. ``http://127.0.0.1:54321``."""
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    @property
    def request_count(self) -> int:
        """Total number of POST /invoice requests received."""
        with self._state.lock:
            return len(self._state.requests)

    @property
    def requests(self) -> list[RecordedRequest]:
        """Snapshot of every request received, in arrival order."""
        with self._state.lock:
            return list(self._state.requests)

    @property
    def invoices(self) -> list[dict[str, Any]]:
        """Snapshot of every invoice actually created (deduplicated by key)."""
        with self._state.lock:
            return list(self._state.invoices_by_key.values())

    def start(self) -> "FakeInvoiceApi":
        """Start serving on a background thread."""
        if self._thread is None:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        """Stop the server and join its thread (idempotent)."""
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def __enter__(self) -> "FakeInvoiceApi":
        return self.start()

    def __exit__(self, *exc_info: object) -> None:
        self.stop()
