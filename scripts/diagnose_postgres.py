import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecommerce_pipeline.ingestion.file_registry import connect_postgres  # noqa: E402
from ecommerce_pipeline.reliability.postgres_diagnostics import (  # noqa: E402
    diagnostics_to_dict,
    load_postgres_diagnostics,
)


def _connection():
    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )
    connection.set_session(readonly=True, autocommit=True)
    return connection


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only PostgreSQL production diagnostics for operator triage."
    )
    parser.add_argument(
        "--long-running-seconds",
        type=int,
        default=60,
        help="Threshold for active/transaction sessions (default: 60 seconds).",
    )
    parser.add_argument(
        "--top-queries",
        type=int,
        default=10,
        help="Number of pg_stat_statements rows to show (default: 10).",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    connection = _connection()
    try:
        diagnostics = load_postgres_diagnostics(
            connection,
            long_running_threshold_seconds=args.long_running_seconds,
            top_query_limit=args.top_queries,
        )
    finally:
        connection.close()

    payload = diagnostics_to_dict(diagnostics)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    connections = payload["connections"]
    print(f"PostgreSQL: {payload['database']} (server {payload['server_version']})")
    print(
        "Connections: "
        f"{connections['total']}/{connections['max_connections']} "
        f"({connections['usage_percent']}%) active={connections['active']} "
        f"idle_in_transaction={connections['idle_in_transaction']} "
        f"waiting={connections['waiting']}"
    )
    print(f"Blocking sessions: {len(payload['blocking_sessions'])}")
    print(f"Long-running sessions: {len(payload['long_running_sessions'])}")
    print(f"Top query fingerprints: {len(payload['top_queries'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
