from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecommerce_pipeline.ingestion.file_registry import connect_postgres  # noqa: E402


def main() -> int:
    connection = connect_postgres(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "ecommerce"),
        user=os.getenv("POSTGRES_USER", "airflow"),
        password=os.getenv("POSTGRES_PASSWORD", "change_me"),
        role=os.getenv("POSTGRES_ROLE", "ecommerce_ingest_writer"),
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(
                """
                SELECT
                    policy_key,
                    data_domain,
                    policy_status,
                    retention_days,
                    enforcement_enabled,
                    rationale
                FROM audit.data_retention_policies
                ORDER BY policy_key
                """
            )
            rows = cursor.fetchall()
    finally:
        connection.rollback()
        connection.close()

    print("policy_key | domain | status | days | enforcement | rationale")
    for key, domain, status, days, enabled, rationale in rows:
        print(
            f"{key} | {domain} | {status} | "
            f"{days if days is not None else '-'} | {enabled} | {rationale}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
