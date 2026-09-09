# PART 10 — Production Airflow Orchestration

## Scope

PART 10 turns the existing `ecommerce_ingestion` DAG into the production-oriented orchestration layer for Project 06.
It keeps ingestion audit ownership unchanged and places dbt transformation after the ingestion teardown boundary.

## Runtime

- Apache Airflow 3.3.0
- LocalExecutor
- PostgreSQL metadata database
- dbt Core 1.12.0
- dbt-postgres 1.11.0
- scheduler-local task execution

Because LocalExecutor launches task subprocesses from the scheduler runtime, dbt is installed in the same Airflow image used by the scheduler.

## Schedule

The DAG uses `CronDataIntervalTimetable` at `02:00 Asia/Bangkok`.
This provides a real daily data interval rather than a zero-length cron trigger interval.

Operational controls:
- `max_active_runs = 1`
- `max_active_tasks = 4`
- DagRun timeout = 2 hours
- DAG is scheduled daily and remains explicitly controllable through pause/unpause

## Task Flow

```text
create audit run
  -> validate runtime
  -> discover files
  -> register/idempotency
  -> extract/schema/DQ/raw load
  -> finalize ingestion audit
  -> resolve dbt runtime context
  -> dbt compile
  -> dbt source freshness
  -> dbt run
  -> blocking dbt tests
  -> warning dbt tests
```

The ingestion teardown is intentionally before dbt. Therefore a successful raw-ingestion audit is not rewritten as failed when a downstream transformation or warehouse test fails.
The final Airflow leaf is the warning-test task, so downstream failure propagates to the DagRun state.

## Resource Isolation

Airflow pools:
- `postgres_ingestion`: 2 slots
- `dbt_transform`: 1 slot

The dbt pool serializes transformations against the shared PostgreSQL warehouse. The ingestion pool prevents unbounded heavy loader concurrency.

## Failure Semantics

The orchestration contract separates two states:

- `audit.ingestion_runs`: truth about raw ingestion only
- Airflow DagRun: truth about the complete end-to-end pipeline

Example:

```text
raw ingestion = success
dbt blocking test = failed
=> ingestion audit = success
=> Airflow DagRun = failed
```

This prevents transformation failure from corrupting ingestion audit meaning.

## Backfill Contract

Airflow backfill data intervals are converted to `Asia/Bangkok` business dates before dbt variables are built.
The resulting values are passed to PART 9 as an end-exclusive window:

```text
backfill_start <= business_date < backfill_end
```

Manual and scheduled runs pass no backfill variables and use normal target-derived incremental watermarks.
