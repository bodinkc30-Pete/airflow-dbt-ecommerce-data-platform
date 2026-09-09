# Performance Runbook

## Purpose

Use this runbook when a scheduled pipeline becomes slower, PostgreSQL shows lock
contention, or a dbt task regresses. Measure first; do not add indexes, increase
memory, or change concurrency before identifying the bottleneck.

## 1. Classify the slowdown

Check the DagRun and task durations first. Separate:

- ingestion/runtime overhead;
- dbt compile/startup time;
- dbt transformation time;
- blocking/warning test time;
- retry/backoff time;
- PostgreSQL SQL execution time.

A long DagRun caused by retry delay is not equivalent to a long SQL statement.
Use the PART 12 incident diagnostics CLI when retries or failures are involved.

## 2. Check PostgreSQL statement telemetry

Confirm `pg_stat_statements` is loaded and query the highest cumulative or mean
execution-time statements. Also inspect shared reads, cache hits, row counts,
and temporary writes.

Reset statement statistics only for a controlled measurement window; resetting
statistics does not change application data.

## 3. Validate planner statistics

For mart tables rebuilt by dbt, verify `pg_stat_user_tables.last_analyze` is
recent. Compare `EXPLAIN (ANALYZE, BUFFERS)` estimates with actual rows.

If estimates are materially wrong, run `ANALYZE` before changing indexes or
planner cost parameters. PART 13 configures an `ANALYZE` post-hook on marts so
normal dbt runs refresh statistics automatically.

## 4. Investigate locks and deadlocks

Search PostgreSQL logs for:

```text
deadlock detected
still waiting
acquired ... lock
process ... waits for
```

Then identify the statements and relations involved. Do not solve a lock problem
by blindly raising retry counts or database memory. Compare dbt concurrency with
actual throughput and lock behavior.

The current evidence-based default is `DBT_THREADS=2`. Revisit this only after a
controlled benchmark on a materially different dataset or workload.

## 5. Evaluate indexes

Add an index only when evidence shows a repeated selective access pattern or
expensive scan at realistic scale. Validate with `EXPLAIN (ANALYZE, BUFFERS)`
before and after the index and account for write/storage overhead.

## 6. Verify after a change

Use the validation chain appropriate to the change:

```text
Compose/dbt configuration validation
→ dbt compile
→ targeted dbt run
→ production Airflow DagRun
→ pg_stat_statements / query plans
→ blocking DQ
→ full regression
```

A performance change is not accepted if it improves runtime while introducing
DQ failures, retries, stale planner statistics, or transaction regressions.

## Current safe baseline

- dbt default threads: 2
- marts statistics: refreshed by dbt post-hook
- PostgreSQL statement telemetry: enabled
- lock-wait logging: enabled
- new marts indexes: none in PART 13

Rebaseline these values when production data volume or workload shape changes.
