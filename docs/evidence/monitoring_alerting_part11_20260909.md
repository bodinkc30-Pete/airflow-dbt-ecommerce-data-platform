# PART 11 — Monitoring and Alerting Evidence — 2026-09-09

## Baseline research

Valid post-PART-10 successful full-DAG runs showed approximately:

- median duration: 51.83 seconds
- p95 duration: 54.19 seconds
- maximum valid duration: 54.36 seconds
- dbt compile p95: 11.12 seconds
- dbt run p95: 9.09 seconds
- blocking DQ p95: 11.20 seconds

Older Airflow metadata contained invalid historical durations where end time was
before start time. Those records were excluded from threshold reasoning.

## Database control plane

`database/schema/10_create_pipeline_monitoring.sql` was applied with
`ON_ERROR_STOP=1` and created:

- `audit.pipeline_monitoring_runs`
- `audit.pipeline_alerts`
- `audit.pipeline_health_latest`
- `audit.open_pipeline_alerts`

PostgreSQL integration tests verified monitoring/alert persistence, idempotent
upsert behavior, delivery-state updates, and transaction neutrality.

## Runtime scenario 1 — normal production run

DagRun: `part11_normal_20260909`

- DagRun: success
- tasks: 13/13 success
- Airflow duration: 59.17 seconds
- monitoring duration: 58.854 seconds
- `is_slow`: false at 180-second threshold
- dbt freshness: 8 pass / 0 warn / 0 error
- dbt blocking: 207 pass / 0 warn / 0 error
- dbt warning tier: 10 pass / 7 warn / 0 error
- monitoring failed/blocked task counts: 0 / 0

`audit.pipeline_health_latest` updated to the run. A `dbt_warning` alert was
persisted with warning severity and `delivery_status=recorded`. Warning external
notification was not requested, and the DagRun remained successful.

## Runtime scenario 2 — slow pipeline

Runtime-only threshold was changed to 1 second; repository defaults remained
unchanged. DagRun `part11_slow_20260909` completed successfully in 54.28 seconds.
Monitoring recorded `is_slow=true`, a `slow_pipeline` warning, and the known
dbt warning. The slow alert requested external notification, but with no webhook
configured its delivery status became `not_configured`; the DagRun stayed success.

## Runtime scenario 3 — blocking failure propagation

A PII-free synthetic Order/SKU probe with `quantity=-1` was inserted under a
separate `run_type=test` audit lineage. DagRun:
`part11_blocking_failure_20260909`.

Observed result:

- ingestion tasks and ingestion finalizer: success
- dbt compile/freshness/run: success
- `dbt_test_blocking`: failed
- `dbt_test_warning`: upstream_failed
- `monitor_pipeline_run`: failed after persisting telemetry
- DagRun: failed
- monitoring failed/blocked task counts: 1 / 1
- application ingestion audit for the Airflow run: manual / success / 0 files

Scheduler logs showed the intended failures:
`non_negative_stg_orders_quantity` FAIL 1 and
`dq_mart_non_negative_measures` FAIL 1, with dbt blocking summary
PASS=205 / ERROR=2. Monitoring persisted a `pipeline_failure` error alert;
with no webhook configured the delivery state was `not_configured`.

## Cleanup and recovery

The synthetic failure probe was deleted in lineage order and the two order facts
were rebuilt with `--full-refresh`. Blocking DQ returned to 207/207 pass.
Residue checks returned zero for the synthetic marker in raw, staging,
intermediate, both order facts, support file audit, and support run audit.

A final normal DagRun, `part11_recovery_20260909`, then completed with 13/13
tasks successful. `audit.pipeline_health_latest` returned to success with
`is_slow=false`, duration 57.216 seconds, and dbt warning count 7.

The intentional failed monitoring run and its alert are retained as operational
evidence. Private source values and PII were not used in the probe.

## Failed-command summary correction

Runtime review found that a failing dbt task originally raised before returning
its parsed summary, so `dbt_blocking_error_count` was incorrectly recorded as 0
even though dbt reported ERROR=2. `DbtCommandError` now preserves command output,
and the Airflow task pushes a dedicated `monitoring_summary` XCom before re-raising.
A second PII-free failure probe confirmed `dbt_blocking_error_count=2`, followed
by cleanup, 207/207 blocking DQ pass, and recovery DagRun
`part11_recovery_summary_20260909` returning latest pipeline health to success.

## Final regression gate

Validation on the final PART 11 working tree:

- dbt build: PASS=250 / WARN=7 / ERROR=0 / TOTAL=257
- Python compile: pass
- Ruff: pass
- pytest: 324 passed
- Airflow import errors: none
- Airflow DAG runtime: 13 tasks, final leaf `monitor_pipeline_run`
- monitor trigger rule: `ALL_DONE`
- timetable: `CronDataIntervalTimetable`
- pipeline slow threshold: 180 seconds
- PostgreSQL latest health: recovery DagRun success
- synthetic PART 11 probe residue: zero across raw, staging, intermediate,
  order facts, support file audit, and support run audit

## Portfolio evidence candidates

High-value README candidates from this phase are the 13-task successful Airflow
run, the blocking-failure run with monitoring propagation, the slow-run alert,
and the recovered latest-health state. Screenshots must use only demo/synthetic
state and must be reviewed for PII, secrets, private filenames, and local paths
before they are added under `docs/assets/readme/monitoring/` or
`docs/assets/readme/airflow/` during portfolio packaging.
