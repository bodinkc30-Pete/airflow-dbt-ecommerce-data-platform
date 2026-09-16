# PART 20.1 — PostgreSQL Production Diagnostics

## Objective

PART 20.1 adds read-only PostgreSQL operator diagnostics without changing the
closed ingestion, dbt, Airflow, transaction, or deployment architecture.
The purpose is production triage: establish database state before remediation.

## Operator contract

The diagnostic surface reports:

- database identity and PostgreSQL server version;
- connection usage versus `max_connections`;
- active, waiting, and idle-in-transaction sessions;
- blocked PID to blocking PID relationships;
- long-running transaction/session age and wait state; and
- `pg_stat_statements` query fingerprints ranked by cumulative execution time.

Both Python and SQL operator paths are observational by design.

## Components

- `src/ecommerce_pipeline/reliability/postgres_diagnostics.py` — typed diagnostic model and read-only queries.
- `scripts/diagnose_postgres.py` — operator CLI with text and JSON output.
- `sql/operations/postgres_diagnostics.sql` — direct SQL triage pack for psql/operators.
- `tests/reliability/test_postgres_diagnostics.py` — unit and CLI contract tests.
- `tests/reliability/test_postgres_diagnostics_sql.py` — read-only SQL safety contract.
- `tests/integration/test_postgres_diagnostics_postgres.py` — live PostgreSQL integration test.

## Safety boundaries

The Python CLI explicitly opens its session as read-only and autocommit-enabled
for observational queries. The module does not own commit/rollback behavior and
does not terminate sessions. The SQL operator pack contains no DDL or DML.

Remediation remains a human/operator decision supported by logs, incident evidence,
and the existing PART 12 incident workflow. A blocker is evidence to investigate,
not authorization to kill a backend automatically.
