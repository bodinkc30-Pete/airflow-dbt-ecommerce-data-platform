# PART 12 Evidence — Reliability and Troubleshooting

Date: 2026-09-09

All runtime probes used demo/synthetic state only. No private customer or
creator data was introduced for reliability validation.

## Research baseline

The production DAG already had retries, exponential backoff, timeouts,
resource pools, concurrency limits, transaction boundaries, monitoring, and
alerts. PART 12 therefore focused on operating those controls rather than
adding a second reliability framework.

Airflow metadata showed that normal dbt transformation runs completed on the
first attempt, while one reliability run completed on attempt 2.

## Runtime scenario 1 — transient retry and recovery

DagRun: `part12_transient_retry_20260909`

Attempt 1 of `dbt_run_transformations` emitted a runtime-only synthetic failure
and raised a `DbtCommandError` with exit code 75. Airflow recorded the task as
`up_for_retry`.

After the configured retry delay, attempt 2 ran successfully:

- `try_number=2`
- `max_tries=2`
- downstream blocking DQ: 207/207 pass
- downstream warning DQ: 10 pass / 7 warn / 0 error
- final DagRun state: success
- DagRun duration: approximately 252.94 seconds

The longer runtime also triggered the monitoring slow-run signal, proving that
reliability recovery and observability remain connected.

## Runtime scenario 2 — timeout enforcement

A temporary Airflow-only probe used `execution_timeout=3s` and intentionally
slept for ten seconds.

Observed log evidence:

- `PART12_TIMEOUT_PROBE: sleeping beyond execution timeout`
- `Process timed out`
- exception type: `AirflowTaskTimeout`
- task state: failed
- DagRun state: failed

The temporary DAG file was deleted after the test.

## Runtime scenario 3 — data-quality incident closure

An earlier PII-free synthetic negative quantity produced a failed DagRun with
blocking order quality errors. PART 12 used that retained monitoring evidence
as a real incident record.

Alert `55` was resolved with:

- root-cause category: `data_quality`
- remediation: remove synthetic lineage and rebuild clean order facts
- recovery DagRun: `part11_recovery_summary_20260909`
- verification: blocking DQ returned to 207/207 pass

The alert-resolution constraint requires root cause, remediation, recovery run,
and verification fields before an alert can remain resolved.

## Incident diagnostics CLI

The read-only CLI successfully joined Airflow metadata with application
monitoring for both the transient retry run and the failed DQ run. It surfaced
DagRun state, duration, task attempts, monitoring state, ingestion state, and
alert resolution status without reading private source rows.

## Portfolio evidence candidates

High-value README/GitHub evidence from this phase:

- Airflow retry run showing `dbt_run_transformations` attempt 2 success
- task log showing attempt 1 `up_for_retry` after transient exit code 75
- diagnostics CLI output combining Airflow and application state
- resolved incident record linking root cause to a verified recovery DagRun
- timeout evidence showing `AirflowTaskTimeout`

The transient-retry recovery is the strongest hero evidence because it shows a
production task failing, Airflow recovering automatically, downstream quality
gates passing, and monitoring detecting the longer runtime. Timeout evidence is
better suited to `docs/evidence/` than the main README.

Any screenshots must use only demo/synthetic state and be checked for PII,
secrets, private filenames, and local filesystem paths before commit. Suggested
future locations are `docs/assets/readme/airflow/` and
`docs/assets/readme/reliability/`.

## Real PostgreSQL deadlock recovery

Final recovery DagRun: `part12_final_recovery_20260909`.

Attempt 1 of `dbt_run_transformations` failed in `stg_orders` with PostgreSQL
`deadlock detected`. The server detail showed two backend processes waiting on
`AccessExclusiveLock` resources held by each other. dbt returned exit code 1
and Airflow moved the task to `up_for_retry`.

Attempt 2 succeeded without code, model, or transaction-boundary changes.
Final runtime state:

- DagRun: success
- Airflow tasks: 13/13 success
- `dbt_run_transformations`: success, try 2/2
- blocking dbt DQ: 207 pass, 0 warn, 0 error
- source freshness: 8 pass, 0 warn, 0 error
- warning tier: 10 pass, 7 warn, 0 error
- monitoring: success, slow=true
- monitored duration: 256.029 seconds

The slow-pipeline signal is expected evidence of retry latency. This incident
proves automatic recovery from a real transient PostgreSQL concurrency failure.
No private source rows, PII, private workspace path, or client identifiers are
included in this evidence.

## Final validation gate

Final validation on the completed PART 12 implementation:

- dbt compile: exit 0; 33 models, 224 data tests, 8 sources
- dbt build: 257/257 completed; PASS=250, WARN=7, ERROR=0, SKIP=0
- Python compileall: exit 0
- Ruff: all checks passed
- pytest: 335 passed
- Airflow DAG import errors: none
- final deadlock-recovery DagRun: success, 13/13 task states success
- incident diagnostics CLI: exit 0 on the final recovery DagRun
- temporary timeout-probe file removed
- stale timeout-probe Airflow metadata deleted after runtime validation

The seven dbt warnings are the existing warning-tier data-quality baseline and
remain non-blocking. The real deadlock incident was resolved with root-cause
category `database` and a verified recovery record; the separate dbt-warning
alert remains unresolved because it represents a different signal.
