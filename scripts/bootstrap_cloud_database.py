from __future__ import annotations

import os
from pathlib import Path

import psycopg2
from psycopg2 import sql

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "database" / "schema"


def _connect(*, database: str, user: str, password: str):
    connection = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=database,
        user=user,
        password=password,
        sslmode=os.getenv("POSTGRES_SSLMODE", "require"),
    )
    connection.autocommit = True
    return connection


def _ensure_runtime_role(connection, *, user: str, password: str) -> None:
    if user != "airflow":
        raise RuntimeError(
            "Cloud runtime database user must remain 'airflow' for the governance contract"
        )

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,))
        exists = cursor.fetchone() is not None
        if not exists:
            role_statement = sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION PASSWORD %s"
            ).format(sql.Identifier(user))
        else:
            role_statement = sql.SQL(
                "ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION PASSWORD %s"
            ).format(sql.Identifier(user))
        cursor.execute(role_statement, (password,))


def _ensure_airflow_database(connection, *, owner: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'airflow'")
        if cursor.fetchone() is None:
            statement = sql.SQL("CREATE DATABASE airflow OWNER {}").format(
                sql.Identifier(owner)
            )
        else:
            statement = sql.SQL("ALTER DATABASE airflow OWNER TO {}").format(
                sql.Identifier(owner)
            )
        cursor.execute(statement)


def _apply_schema(connection) -> None:
    migrations = sorted(SCHEMA_DIR.glob("*.sql"))
    if not migrations:
        raise RuntimeError(f"No schema migrations found in {SCHEMA_DIR}")

    for path in migrations:
        with connection.cursor() as cursor:
            cursor.execute(path.read_text(encoding="utf-8"))
        print(f"applied={path.relative_to(ROOT).as_posix()}")


def main() -> int:
    master_user = os.environ["RDS_MASTER_USER"]
    master_password = os.environ["RDS_MASTER_PASSWORD"]
    runtime_user = os.environ["POSTGRES_USER"]
    runtime_password = os.environ["POSTGRES_PASSWORD"]

    admin = _connect(database="ecommerce", user=master_user, password=master_password)
    try:
        _ensure_runtime_role(admin, user=runtime_user, password=runtime_password)
        _ensure_airflow_database(admin, owner=runtime_user)
        _apply_schema(admin)
    finally:
        admin.close()

    print("cloud_database_bootstrap=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
