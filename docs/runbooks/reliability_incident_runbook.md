# Reliability Incident Runbook

## Goal

Use this runbook when an Airflow DagRun fails, retries, times out, or produces a
pipeline alert that requires engineering investigation.

## 1. Diagnose the run

Run the diagnostics CLI with the Python environment that contains project
dependencies:

```bash
python scripts/diagnose_pipeline_run.py --dag-run-id <run-id>
```

For machine-readable output:

```bash
python scripts/diagnose_pipeline_run.py --dag-run-id <run-id> --json
```

Check the DagRun state, failed or blocked tasks, task attempt numbers,
monitoring status, ingestion status, and alerts before changing data or code.

## 2. Classify the root cause

Use one of the supported categories:

- `transient_dependency`
- `database`
- `data_quality`
- `schema`
- `transformation`
- `orchestration`
- `timeout`
- `resource`
- `configuration`
- `unknown`

Do not classify from symptoms alone. Read the failing task log and identify the
first actionable error before selecting a category.

## 3. Recover with the existing contract

Prefer the narrowest safe recovery:

- transient failure: allow configured retry when the task is idempotent
- bad synthetic/source row: remove only the offending lineage, then rebuild
- transformation failure: correct the model or dependency, then rerun
- timeout: determine whether the task is hung or the timeout is undersized

## 4. Verify recovery

Do not close the incident because a retry merely started. Verify the resulting
state with the relevant gates, for example:

```text
Airflow task/DagRun state
→ dbt blocking DQ
→ row-count/reconciliation checks
→ monitoring latest health
→ synthetic residue check when a probe was used
```

The recovery DagRun must be identifiable so the incident record can link the
failure to the verified recovery.

## 5. Resolve the alert

A resolved alert must record:

- root-cause category and summary
- remediation summary
- recovery DagRun ID
- verification summary
- optional structured resolution details

`resolve_pipeline_alert()` is transaction-neutral; the caller owns commit or
rollback through the existing application transaction contract.

## PostgreSQL deadlock response

When dbt reports `deadlock detected`, do not immediately reduce concurrency or
change transaction ownership. First capture the failing model, lock type,
backend wait cycle, dbt exit code, Airflow task attempt, and whether the retry
recovers.

Classify a recovered deadlock as a transient database incident only when the
next attempt succeeds and downstream blocking quality gates are green. Record
the recovery DagRun or retry attempt in the incident evidence.

Escalate to PART 13 performance/locking analysis if deadlocks recur, exhaust
retries, affect multiple models, or materially violate the pipeline runtime
objective. Any concurrency change must be supported by repeated runtime and
lock evidence rather than a single recovered event.
