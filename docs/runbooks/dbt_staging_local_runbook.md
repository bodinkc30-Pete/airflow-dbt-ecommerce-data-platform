# dbt Staging Local Runbook

## Purpose

Run and validate PART 4 staging transformations against the local PostgreSQL service.

## Prerequisites

- PostgreSQL container is healthy on localhost:5432.
- Install `requirements-dbt.txt` in the local Python environment.
- Run commands from the repository root.

## Commands

```powershell
dbt debug --project-dir dbt --profiles-dir dbt
dbt compile --project-dir dbt --profiles-dir dbt
dbt run --project-dir dbt --profiles-dir dbt --select staging
dbt test --project-dir dbt --profiles-dir dbt
```

Expected output schema: `analytics_staging`.

## Failure behavior

Safe-cast macros convert malformed text to `NULL`; they do not modify raw rows. Investigate unexpected parse-null counts before adding downstream business rules.

Airflow does not execute dbt in PART 4. Airflow/dbt orchestration is intentionally deferred to PART 10.
