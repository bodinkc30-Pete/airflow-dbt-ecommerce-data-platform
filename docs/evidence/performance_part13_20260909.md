# PART 13 — Performance Evidence — 2026-09-09

## Baseline

Environment measured during this phase:

- PostgreSQL 17.10
- dbt Core 1.12.0 / dbt-postgres 1.11.0
- Airflow 3.3.0 with LocalExecutor
- original dbt default: 4 threads
- current demo order facts: 3 rows

Representative normal DagRuns before retry incidents generally completed in
about 50–60 seconds. dbt task p95 values were approximately 12.6 seconds for
compile, 10.5 seconds for transformations, 13.6 seconds for blocking tests,
6.4 seconds for warning tests, and 6.3 seconds for freshness.

The two PART 12 retry runs lasted about 253–256 seconds because retry delay and
backoff dominated total runtime; they were not evidence that SQL itself took four
minutes.

## PostgreSQL baseline

Observed settings before tuning included 4 MB `work_mem`, 128 MB
`shared_buffers`, `deadlock_timeout=1s`, `track_io_timing=off`, and
`log_lock_waits=off`. `pg_stat_statements` was available in the image but not
enabled.

## Query-plan measurements

Representative mart queries executed in approximately 0.05–0.66 ms on the
demo dataset. PostgreSQL chose sequential scans, which is appropriate for these
very small relations. No index was added from these measurements.

Before `ANALYZE`, one calendar query estimated 217 rows from `dim_date` while
returning 26. After `ANALYZE`, the estimate was 26 and execution dropped from
about 0.56 ms to about 0.08 ms on the same query shape.

A separate product aggregation showed `dim_product` estimated at 380 rows while
only 3 existed after repeated dbt table rebuilds. This demonstrated that rebuilt
mart tables could lose useful planner statistics.

Running `ANALYZE` across all 11 marts completed in about 0.136 seconds. After
adding the dbt post-hook, a targeted `dim_product` build immediately populated
`last_analyze` and `n_live_tup=3`.

## Concurrency benchmark

Eighteen controlled `dbt run` executions produced:

| Threads | Runs | Failures | Min | Average | Max |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 6 | 0 | 8.416 s | 11.715 s | 21.009 s |
| 2 | 6 | 0 | 7.879 s | 8.728 s | 9.410 s |
| 4 | 6 | 0 | 8.337 s | 8.975 s | 9.766 s |

Two threads therefore matched or slightly beat four threads for the current
workload. Combined with the real PART 12 PostgreSQL deadlock at four threads,
this justified reducing the default to 2 without sacrificing measured throughput.

## PostgreSQL observability runtime

The PostgreSQL container was recreated with:

```text
shared_preload_libraries=pg_stat_statements
track_io_timing=on
log_lock_waits=on
```

Migration `12_enable_performance_observability.sql` completed with exit code 0
and installed `pg_stat_statements` version 1.11. The extension returned live
query statistics immediately after enablement.

After resetting only statement statistics, a production Airflow run was executed
with the new settings. `pg_stat_statements` captured dbt nodes, execution time,
shared-buffer activity, rows, and temporary writes. No temporary-block writes
were observed in the top measured dbt workload.

The largest measured dbt node by total SQL execution time was `dim_date`, at
roughly 84 ms across its recorded statements. This reinforces that the 8–13
second Airflow dbt task durations are dominated by dbt/process orchestration,
not slow individual warehouse SQL in the demo dataset.

## Production Airflow validation after tuning

DagRun `part13_after_tuning_20260909` completed successfully:

- 13/13 tasks succeeded
- total DagRun duration: about 63.25 seconds
- monitoring duration: about 63.00 seconds
- `dbt_run_transformations`: attempt 1, about 8.90 seconds
- blocking errors: 0
- warning-tier dbt warnings: 7, matching the existing baseline
- failed tasks: 0
- blocked tasks: 0

All 11 marts had fresh `last_analyze` timestamps from the dbt post-hook after the
production run. PostgreSQL logs contained no `deadlock detected` or prolonged
lock-wait messages during the post-tuning run.

This single production run is not treated as proof that deadlocks are impossible.
The accepted conclusion is narrower: the safer two-thread default retained the
measured throughput range and the validated production run completed without a
retry or lock incident.

## Portfolio evidence candidates

High-value GitHub evidence from PART 13:

- concurrency benchmark table: 1 vs 2 vs 4 threads;
- PART 12 deadlock followed by PART 13 evidence-based concurrency decision;
- `pg_stat_statements` top dbt node output;
- planner estimate before/after `ANALYZE`;
- Airflow post-tuning run with 13/13 success and dbt attempt 1.

## Final validation gate

Final validation on the commit-ready implementation:

- Docker Compose configuration: pass
- dbt compile: pass with default concurrency 2
- full dbt build: 250 pass / 7 warn / 0 error / 257 total
- Python compileall: pass
- Ruff: pass
- pytest: 341 passed
- Airflow DAG import errors: none
- production scheduler `DBT_THREADS`: 2
- PostgreSQL `pg_stat_statements`: version 1.11 active
- PostgreSQL `track_io_timing`: on
- PostgreSQL `log_lock_waits`: on
- marts with current `last_analyze`: 11/11
- active production DagRuns at final snapshot: 0

The seven dbt warnings remain the previously accepted warning-tier data-quality
signals and are not performance regressions. No raw private data or PII was
required for PART 13 measurements.
