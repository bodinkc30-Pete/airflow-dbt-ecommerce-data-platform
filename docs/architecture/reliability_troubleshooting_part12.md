# PART 12 — Reliability, Recovery, and Troubleshooting

## Purpose

PART 12 turns the existing production Airflow pipeline into an operable system
with repeatable incident diagnosis, recovery, verification, and closure.

The phase does not replace Airflow retry, timeout, pool, or transaction
controls already established in earlier parts. It adds the operational layer
needed to explain what failed, why it failed, how it recovered, and how the
recovery was verified.

## Existing reliability controls

The production DAG already provides:

- `max_active_runs=1` and `max_active_tasks=4`
- PostgreSQL and dbt resource pools
- task execution timeouts
- a two-hour DagRun timeout
- two retries on the idempotent dbt transformation task
- exponential retry backoff with a maximum delay
- caller-owned PostgreSQL transaction boundaries
- durable monitoring snapshots and pipeline alerts

## Incident control plane

`audit.pipeline_alerts` is extended with durable incident-closure fields:

- `root_cause_category`
- `root_cause_summary`
- `remediation_summary`
- `recovery_dag_run_id`
- `verification_summary`
- `resolution_details`

A resolved alert must contain a complete root-cause and recovery record. The
constraint prevents an alert from being marked resolved with only a timestamp.

## Diagnostic model

`incident_diagnostics.py` reads both control planes:

1. Airflow metadata for DagRun state, task state, attempts, and duration.
2. Application PostgreSQL for ingestion status, monitoring state, and alerts.

The read-only CLI exposes the combined view without querying private source
rows. It can render compact text for incident response or JSON for automation.

## Recovery patterns validated in this phase

### Transient transformation failure

A runtime-only dbt failure on attempt 1 transitioned to `up_for_retry`. Airflow
retried the same idempotent task and attempt 2 succeeded. Downstream blocking
DQ then passed and the DagRun completed successfully.

### Blocking data-quality incident

A PII-free synthetic negative quantity caused blocking dbt tests to fail. The
bad synthetic lineage was removed, order facts were rebuilt, blocking DQ
returned to green, and a later recovery DagRun verified the platform state.

### Hung-task timeout

A temporary Airflow probe intentionally exceeded a three-second
`execution_timeout`. Airflow raised `AirflowTaskTimeout` and failed the DagRun.
The probe DAG was removed after validation and is not part of the product DAG.

## Boundary

Performance tuning remains PART 13. Security/governance and deployment
hardening remain later roadmap phases. PART 12 is limited to reliability,
incident response, diagnosis, recovery, and verification.

## Observed PostgreSQL deadlock recovery

A later clean recovery run produced a real PostgreSQL deadlock while dbt was
building `stg_orders` concurrently with other relations. PostgreSQL reported a
cycle involving `AccessExclusiveLock` waits, dbt exited non-zero, and Airflow
moved `dbt_run_transformations` to `up_for_retry`.

The configured retry policy recovered without a model or transaction-contract
change: attempt 2 succeeded, all 13 Airflow tasks finished successfully,
blocking dbt DQ passed 207/207, and source freshness passed 8/8. The longer
recovery duration was independently detected by PART 11 as a slow pipeline.

This incident is treated as reliability evidence, not as justification to tune
dbt concurrency in PART 12. Locking and performance changes require dedicated
measurement and belong to PART 13.
