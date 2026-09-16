from datetime import UTC, datetime

from ecommerce_pipeline.reliability.postgres_diagnostics import (
    diagnostics_to_dict,
    load_postgres_diagnostics,
)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        if "SELECT current_database()," in query:
            self.rows = [("ecommerce", "17.10")]
        elif "max_connections" in query:
            self.rows = [(12, 3, 1, 2, 100)]
        elif "pg_blocking_pids" in query:
            self.rows = [(501, 601, 42.5)]
        elif "long_running" in query:
            self.rows = [(701, "active", "Lock", "transactionid", 90.0)]
        elif "pg_stat_statements" in query:
            self.rows = [(12345, 7, 140.0, 20.0, 77)]
        else:
            raise AssertionError(query)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class FakeConnection:
    def __init__(self):
        self.queries = []

    def cursor(self):
        return FakeCursor(self)


def test_load_postgres_diagnostics_combines_operational_signals() -> None:
    connection = FakeConnection()
    captured_at = datetime(2026, 9, 17, tzinfo=UTC)

    result = load_postgres_diagnostics(
        connection,
        long_running_threshold_seconds=60,
        top_query_limit=5,
        captured_at=captured_at,
    )

    assert result.database == "ecommerce"
    assert result.server_version == "17.10"
    assert result.connections.total == 12
    assert result.connections.active == 3
    assert result.connections.idle_in_transaction == 1
    assert result.connections.waiting == 2
    assert result.connections.max_connections == 100
    assert result.connections.usage_percent == 12.0
    assert result.blocking_sessions[0].blocked_pid == 501
    assert result.blocking_sessions[0].blocker_pid == 601
    assert result.long_running_sessions[0].pid == 701
    assert result.top_queries[0].query_id == 12345
    assert result.top_queries[0].mean_exec_time_ms == 20.0


def test_diagnostics_to_dict_is_json_ready() -> None:
    result = load_postgres_diagnostics(
        FakeConnection(),
        long_running_threshold_seconds=60,
        top_query_limit=5,
        captured_at=datetime(2026, 9, 17, tzinfo=UTC),
    )

    payload = diagnostics_to_dict(result)

    assert payload["database"] == "ecommerce"
    assert payload["connections"]["usage_percent"] == 12.0
    assert payload["blocking_sessions"][0]["blocker_pid"] == 601
    assert payload["top_queries"][0]["query_id"] == 12345
    assert payload["captured_at"] == "2026-09-17T00:00:00+00:00"


def test_postgres_diagnostics_cli_exposes_read_only_operator_options() -> None:
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "diagnose_postgres.py"), "--help"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "read-only" in result.stdout.lower()
    assert "--long-running-seconds" in result.stdout
    assert "--top-queries" in result.stdout
    assert "--json" in result.stdout
