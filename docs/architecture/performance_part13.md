# PART 13 — Performance Architecture

## Objective

PART 13 hardens performance using measured evidence rather than speculative tuning.
The scope covers PostgreSQL observability, dbt concurrency, planner statistics,
and production runtime validation. It does not change warehouse grain or the
closed ingestion/dbt architecture.

## Evidence-driven decisions

The demo warehouse is intentionally small: current order facts contain only a
few rows and representative warehouse queries execute in well under 1 ms.
Therefore no new business-query indexes are added in this phase.

The measurable risks were instead:

- production dbt concurrency had experienced a real PostgreSQL deadlock;
- table materialization discarded fresh planner statistics on rebuilt marts;
- PostgreSQL query and I/O telemetry was not retained for investigation.

## dbt concurrency

Controlled `dbt run` benchmarks used six runs at each thread count:

| Threads | Failures | Average runtime |
| ---: | ---: | ---: |
| 1 | 0 | 11.715 s |
| 2 | 0 | 8.728 s |
| 4 | 0 | 8.975 s |

Two threads matched or slightly improved the measured four-thread workload while
reducing concurrent DDL pressure. Production and local defaults are therefore 2.

## Planner statistics

All marts use a dbt post-hook:

```sql
analyze {{ this }}
```

This keeps PostgreSQL statistics current after table rebuilds and incremental
writes. A controlled comparison showed `dim_date` cardinality estimation improve
from 217 estimated rows versus 26 actual rows to an estimate of 26 after
`ANALYZE`. Running `ANALYZE` across all 11 marts took about 0.136 seconds in the
demo environment.

## PostgreSQL observability

The PostgreSQL service starts with:

- `shared_preload_libraries=pg_stat_statements`
- `track_io_timing=on`
- `log_lock_waits=on`

Migration `12_enable_performance_observability.sql` enables
`pg_stat_statements` in the application database. The extension provides query
execution counts, timings, block I/O counters, row counts, and temporary-block
activity for production diagnosis.

`log_lock_waits` complements PART 12 incident diagnostics by making prolonged
lock waits visible in PostgreSQL logs before they become unexplained latency.

## Production runtime behavior

After tuning, a full Airflow production run completed successfully with all 13
tasks green and `dbt_run_transformations` succeeding on attempt 1. The run took
about 63 seconds end to end; dbt execution itself remained around 9 seconds.
No deadlock or lock-wait messages were emitted during that run.

The goal of the thread reduction is reliability without measured throughput loss,
not claiming that every future workload will be faster. Larger datasets must be
remeasured before further concurrency changes.

## Index policy

No new marts indexes are added because current representative queries execute
below 1 ms and PostgreSQL correctly prefers sequential scans on tiny relations.
Indexes require evidence from larger workloads, selective predicates, repeated
query patterns, or `pg_stat_statements` before being introduced.

## Boundaries

PART 13 does not change fact/dimension grain, incremental semantics, transaction
ownership, retry policy, or monitoring severity. Governance/security remain
PART 14 and deployment hardening remains PART 15.
