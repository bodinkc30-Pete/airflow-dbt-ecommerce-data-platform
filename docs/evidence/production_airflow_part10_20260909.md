# PART 10 — Production Airflow Runtime Evidence

Date: 2026-09-09

All scenarios used portfolio-safe demo/no-op or synthetic data. No private source values are recorded here.

## Container Runtime

Verified inside `airflow-scheduler`:
- Airflow 3.3.0
- dbt Core 1.12.0
- dbt-postgres 1.11.0
- `dbt debug` PostgreSQL connection: PASS

Verified Airflow pools:
- `postgres_ingestion`: 2 slots
- `dbt_transform`: 1 slot

## Execution API Failure and Recovery

Initial LocalExecutor run failed before user code with:

```text
httpx.ConnectError: [Errno 111] Connection refused
```

Airflow 3.3 source inspection showed LocalExecutor derives the execution API from `[api] base_url` and otherwise defaults to `http://localhost:8080/execution/`.
The API server is a separate Compose service, so scheduler-local `localhost:8080` was invalid.

Fix:

```text
AIRFLOW__API__BASE_URL=http://airflow-api-server:8080
```

After scheduler recreation, effective execution URL became:

```text
http://airflow-api-server:8080/execution/
```

LocalExecutor task execution then proceeded normally.

## Manual End-to-End Success

Run ID: `part10_manual_20260909_v2`

Result:
- DagRun: SUCCESS
- tasks: 12/12 SUCCESS
- duration: approximately 53 seconds
- ingestion files discovered: 0
- ingestion audit: SUCCESS

The successful chain included raw-ingestion lifecycle, dbt compile, source freshness, dbt transformations, blocking DQ, warning DQ, and audit finalization.

## Backfill Runtime

The original cron string produced a zero-length interval in Airflow 3.3 backfill testing. The DAG was changed to `CronDataIntervalTimetable`.

Successful run:

```text
backfill__2026-09-05T19:00:00+00:00
```

Observed data interval:
- start: 2026-09-05 02:00 Asia/Bangkok
- end: 2026-09-06 02:00 Asia/Bangkok

`resolve_dbt_runtime_context` returned:

```text
backfill_start=2026-09-05
backfill_end=2026-09-06
```

Result:
- DagRun: SUCCESS
- tasks: 12/12 SUCCESS
- dbt execution mode: backfill
- duration: approximately 50 seconds

## Downstream Failure Propagation

Run ID: `part10_dbt_failure_20260909`

A synthetic order with `quantity = -1` was inserted under dedicated test-only audit lineage.

Observed result:
- ingestion tasks: SUCCESS
- ingestion finalizer: SUCCESS
- dbt compile/freshness/run: SUCCESS
- `dbt_test_blocking`: FAILED
- `dbt_test_warning`: upstream_failed
- Airflow DagRun: FAILED

Blocking dbt results included:
- `non_negative_stg_orders_quantity`: FAIL 1
- `dq_mart_non_negative_measures`: FAIL 1

Application ingestion audit `1413` remained `manual / success / 0 files`, proving downstream failure does not rewrite raw-ingestion truth.

After the scenario, the synthetic raw row and its supporting test audit file/run were deleted, order facts were full-refreshed, and blocking DQ returned to 207/207 PASS.

Final probe residue across raw, staging, intermediate, marts, and synthetic support audit records: 0.

## Final Regression Gate

Final validation from the completed PART 10 working tree:

- Docker Compose config validation: PASS
- dbt debug from Airflow scheduler: PASS
- PostgreSQL dbt connection: PASS
- dbt compile: PASS
- dbt source freshness: 8/8 PASS
- full dbt build: 250 PASS / 7 WARN / 0 ERROR / 257 total
- Python compile: PASS
- Ruff: PASS
- pytest regression: 309 passed
- Airflow DAG import errors: none

The 7 dbt warnings are the established PART 8 non-blocking anomaly policy and were not introduced by PART 10.

## Final Operational Snapshot

Verified after all runtime scenarios and final regression:

- PostgreSQL container: healthy
- Airflow API server: healthy
- scheduler: running
- DAG processor: running
- triggerer: running
- DAG paused state: false
- timetable: `CronDataIntervalTimetable` (`0 2 * * *`)
- final DAG leaf: `dbt_test_warning`
- `postgres_ingestion` pool: 2 slots
- `dbt_transform` pool: 1 slot
- dbt transformation retries: 2
- dbt retry mode: exponential backoff
- dbt transformation timeout: 45 minutes
- DAG max active runs: 1
- DAG max active tasks: 4
- DagRun timeout: 2 hours
- DAG import errors: none
