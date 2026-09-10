from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "database/schema"
SEED_FILE = ROOT / "database" / "ci" / "seed_synthetic.sql"


def _connect():
    connection = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
    )
    connection.autocommit = True
    return connection


def _execute_file(connection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    with connection.cursor() as cursor:
        cursor.execute(sql)
    print(f"applied={path.relative_to(ROOT).as_posix()}")


def _schema_files() -> list[Path]:
    files = sorted(SCHEMA_DIR.glob("*.sql"))
    if not files:
        raise RuntimeError(f"No schema migrations found in {SCHEMA_DIR}")
    return files


def _verify_seed(connection) -> None:
    query = """
        SELECT
            (SELECT COUNT(*) FROM raw.orders),
            (SELECT COUNT(*) FROM raw.shop_daily),
            (SELECT COUNT(*) FROM raw.campaign_daily),
            (SELECT COUNT(*) FROM raw.live_daily),
            (SELECT COUNT(*) FROM raw.product_card_daily),
            (SELECT COUNT(*) FROM raw.products),
            (SELECT COUNT(*) FROM raw.skus),
            (SELECT COUNT(*) FROM raw.influencer_roster)
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        counts = tuple(int(value) for value in cursor.fetchone())

    if counts != (1, 1, 1, 1, 1, 1, 1, 1):
        raise RuntimeError(f"Unexpected CI seed row counts: {counts}")
    print("synthetic_seed_counts=1,1,1,1,1,1,1,1")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a clean CI PostgreSQL database.")
    parser.add_argument("--seed", action="store_true", help="Load the synthetic CI seed.")
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Apply the schema migration set this many times to verify idempotency.",
    )
    args = parser.parse_args()

    if args.repeat < 1:
        parser.error("--repeat must be at least 1")

    migrations = _schema_files()
    connection = _connect()
    try:
        for iteration in range(1, args.repeat + 1):
            print(f"schema_pass={iteration}")
            for path in migrations:
                _execute_file(connection, path)
        if args.seed:
            _execute_file(connection, SEED_FILE)
            _verify_seed(connection)
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
