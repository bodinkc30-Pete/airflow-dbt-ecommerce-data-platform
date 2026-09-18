# Postmortem — Real PostgreSQL Deadlock Recovery (2026-09)

> Scope note: this postmortem documents a **real incident** in the project's
> production-style Airflow/dbt/PostgreSQL environment on 2026-09-09 — not a
> drill and not a synthetic failure injection. A genuine PostgreSQL deadlock
> aborted a dbt model build during DagRun `part12_final_recovery_20260909`,
> and the platform's existing retry policy recovered automatically. All
> quantitative claims below come from recorded runtime evidence; where the
> evidence has no absolute clock timestamps, relative offsets are used and
> labelled as such. Primary evidence:
> [PART 12 reliability evidence](../evidence/reliability_troubleshooting_part12_20260909.md)
> ("Real PostgreSQL deadlock recovery") and the follow-up
> [PART 13 performance evidence](../evidence/performance_part13_20260909.md).

## Summary

Attempt 1 of `dbt_run_transformations` failed while building `stg_orders`
with a real PostgreSQL `deadlock detected` error: the server detail showed
two backend processes waiting on `AccessExclusiveLock` resources held by each
other. dbt returned exit code 1 and Airflow moved the task to `up_for_retry`.
Attempt 2 succeeded with no code, model, or transaction-boundary changes, and
the DagRun finished with 13/13 Airflow tasks successful and all blocking
quality gates green. The single most important takeaway: the existing retry
policy recovered from a genuine transient database concurrency failure
exactly as designed — the correct response was to capture evidence and verify
recovery, not to change concurrency or transaction contracts under pressure.

## Impact

One dbt transformation task attempt was lost; no models were left in a failed
state, no downstream consumers received late or bad data, and no business
stakeholders were affected — the run completed successfully after one retry.
Quantified impact from the evidence:

- 1 failed attempt of `dbt_run_transformations` (exit code 1), recovered on
  try 2/2.
- Total monitored DagRun duration: 256.029 seconds — longer than a normal run
  because retry delay and backoff dominated the runtime, not because SQL was
  slow (normal runs complete in roughly 50–60 seconds per the
  [PART 13 evidence](../evidence/performance_part13_20260909.md)).
- The monitoring slow-pipeline signal fired (`slow=true`) as expected
  evidence of retry latency.
- No data-quality impact: blocking dbt DQ finished 207 pass / 0 warn /
  0 error after recovery.

## Severity

SEV3 — limited impact, per the SEV definitions in the
[Incident Response Runbook](../runbooks/incident_response_runbook.md): a
single non-recurring task failure with a working automatic workaround (the
configured retry), green downstream quality gates, and primary
decision-making unaffected. It does not meet the runbook's SEV2 example of
"recurring lock contention blocking a critical task": this was one deadlock
event, it did not exhaust retries, and it did not recur in the same run.
Severity stayed at SEV3 throughout; the
[Reliability Incident Runbook](../runbooks/reliability_incident_runbook.md)
("PostgreSQL deadlock response") classifies a deadlock as a transient
database incident precisely when the next attempt succeeds and downstream
blocking gates are green, which held here.

## Timeline

Absolute clock times were not recorded for this incident; the offsets below
are reconstructed from the recorded runtime evidence, all on 2026-09-09.

| Time | Event |
| --- | --- |
| T+0 | DagRun `part12_final_recovery_20260909` executing; `dbt_run_transformations` attempt 1 building models concurrently |
| Attempt 1 | PostgreSQL deadlock detector fired during `stg_orders`: two backend processes waiting on `AccessExclusiveLock` resources held by each other; dbt returned exit code 1 |
| After failure | Airflow recorded the task as `up_for_retry` (try 1/2 consumed) |
| After configured retry delay | Attempt 2 ran and succeeded — no code, model, or transaction-boundary changes |
| Post-retry | Downstream gates green: blocking DQ 207/207 pass, source freshness 8/8 pass, warning tier 10 pass / 7 warn / 0 error |
| T+256.029s (monitored duration) | DagRun finished: success, 13/13 Airflow tasks success; monitoring state success with `slow=true` |
| Post-run | Incident resolved with root-cause category `database` and a verified recovery record |

## Detection

Detection was layered and fully automated:

1. **PostgreSQL deadlock detector** aborted one of the deadlocked backends
   (`deadlock detected`), which surfaced to dbt as a command failure.
2. **Airflow** recorded the task failure and applied the configured retry
   policy (`up_for_retry`, then try 2/2).
3. **Pipeline monitoring** independently flagged the longer runtime as a slow
   pipeline (`slow=true`, monitored duration 256.029 seconds), keeping
   reliability recovery and observability connected.

No human discovered the incident first; every signal that fired came from
existing automation. There was no dedicated deadlock alert — the deadlock was
visible through the task failure it caused (see monitoring gaps below).

## Root Cause

A genuine transient database concurrency conflict (root-cause category:
`database`). While dbt was building `stg_orders` concurrently with other
relations, two backend processes each held an `AccessExclusiveLock` the other
was waiting for. PostgreSQL's deadlock detector broke the cycle by aborting
one backend, dbt exited with code 1, and Airflow retried. The deadlock was a
timing-dependent interaction between concurrent `AccessExclusiveLock`
acquisitions, not a model defect, data defect, or transaction-contract bug —
attempt 2 succeeded with zero changes to code, models, or transaction
boundaries, which is the strongest evidence the cause was transient
concurrency rather than deterministic logic.

## Contributing Factors

- **Concurrent DDL-style lock acquisition:** dbt was rebuilding multiple
  relations concurrently, and `stg_orders` collided with another build taking
  an `AccessExclusiveLock`. The dbt default thread count at the time was 4
  (per the PART 13 baseline), which shapes how many relations build in
  parallel.
- **Limited lock observability at the time of the incident:** the PostgreSQL
  baseline had `log_lock_waits=off` and `pg_stat_statements` not yet enabled,
  so lock-wait history around the deadlock was not being logged.
- **No prior recurrence data:** this was the first observed deadlock, so
  there was no baseline for how often the lock cycle occurs.

## Mitigation

The immediate mitigation was the platform's existing narrowest safe action:
let the configured Airflow retry policy rerun the failed task. No session was
manually terminated, no concurrency setting was changed mid-incident, and no
model or transaction contract was edited — matching the
[Reliability Incident Runbook](../runbooks/reliability_incident_runbook.md)
rule that a first deadlock is handled by capturing the failing model, lock
type, backend wait cycle, exit code, and task attempt, then observing whether
the retry recovers, rather than reacting with an unmeasured concurrency
change.

## Recovery

Recovery was automatic: attempt 2 of `dbt_run_transformations` succeeded on
the same DagRun, `part12_final_recovery_20260909`, which is the recovery run
of record for this incident (see the
[PART 12 evidence](../evidence/reliability_troubleshooting_part12_20260909.md)).
No quarantine, rebuild, or manual intervention was required. The incident was
then resolved with root-cause category `database` and a verified recovery
record, satisfying the alert-resolution contract (root cause, remediation,
recovery run, verification).

## Verification

Recovery was verified by end-state evidence, not just a started retry:

- Final DagRun state: **success**, 13/13 Airflow tasks success.
- `dbt_run_transformations`: success, try 2/2.
- Blocking dbt DQ: **207 pass, 0 warn, 0 error**.
- Source freshness: **8 pass, 0 warn, 0 error**.
- Warning tier: 10 pass / 7 warn / 0 error (the 7 warnings are the
  pre-existing accepted warning-tier baseline, not incident damage).
- Monitoring: success, `slow=true`, monitored duration 256.029 seconds.
- PART 12 final validation gate: dbt build 257/257 (PASS=250, WARN=7,
  ERROR=0), pytest 335 passed, no Airflow DAG import errors, and the
  incident diagnostics CLI exited 0 on the final recovery DagRun.

## Why Monitoring Did or Did Not Catch It

Monitoring caught the *consequence* of the deadlock — the task failure was
recorded by Airflow and the retry latency was flagged by the slow-pipeline
signal — but there was no signal that named the *cause*. At the time of the
incident `log_lock_waits` was off and `pg_stat_statements` was not enabled,
so lock waits were not logged and statement-level history was unavailable;
the deadlock's `AccessExclusiveLock` cycle is known only from the server's
error detail returned to dbt. The corrective actions below close this gap:
PART 13 enabled `log_lock_waits=on`, `track_io_timing=on`, and
`pg_stat_statements`, so a future lock incident leaves queryable evidence.

## Corrective Actions

| Action | Owner | Due date |
| --- | --- | --- |
| Capture deadlock evidence (failing model, lock type, wait cycle, exit code, task attempt, retry outcome) per the deadlock-response runbook | Data engineering | Done 2026-09-09 |
| Resolve the incident with root-cause category `database` linked to the verified recovery DagRun | Data engineering | Done 2026-09-09 |
| PART 13 concurrency benchmark: 18 controlled `dbt run` executions at 1/2/4 threads (0 failures), then reduce the dbt default from 4 to 2 threads — justified by this deadlock at 4 threads with no measured throughput loss | Data engineering | Done 2026-09-09 |
| Enable PostgreSQL lock/statement observability: `log_lock_waits=on`, `track_io_timing=on`, `pg_stat_statements` 1.11 via migration `12_enable_performance_observability.sql` | Data engineering | Done 2026-09-09 |
| Post-tuning validation: DagRun `part13_after_tuning_20260909` — 13/13 success, `dbt_run_transformations` attempt 1 (~8.90 s), no `deadlock detected` in PostgreSQL logs | Data engineering | Done 2026-09-09 |
| PART 20.2 lock failure drills: permanent blocked-PID → blocker-PID detection drill in `tests/failure/test_postgres_lock_incident.py` (see the [lock contention drill postmortem](../postmortems/2026-09_postgres_lock_contention.md)) | Data engineering | Done 2026-09-17 |
| Standing rule: escalate to performance/locking analysis if deadlocks recur, exhaust retries, affect multiple models, or violate the pipeline runtime objective | Data engineering | Open — standing escalation rule |

## Regression Prevention

- **Retry contract:** `dbt_run_transformations` retains its configured retry
  policy (max 2 tries); the incident record proves it works against a real
  deadlock, not just a synthetic transient failure.
- **Blocking quality gates:** the 207 blocking DQ tests and 8 source
  freshness checks must stay green before a recovered run is considered
  healthy — they are the verification bar used here.
- **Lower default concurrency:** the dbt default is now 2 threads, validated
  by the PART 13 benchmark and the post-tuning production run, reducing the
  window for concurrent `AccessExclusiveLock` cycles without measured
  throughput loss.
- **Lock observability:** `log_lock_waits=on` and `pg_stat_statements` mean a
  recurrence now produces log and statement evidence.
- **Drill coverage:** the PART 20.2 failure-drill suite
  (`tests/failure/test_postgres_lock_incident.py`) re-verifies lock-detection
  behavior on every PostgreSQL integration run, and the
  [Reliability Incident Runbook](../runbooks/reliability_incident_runbook.md)
  escalation rule converts any recurrence into a measured analysis task
  instead of an ad-hoc reaction.

## Lessons Learned

**What went well:** the retry policy recovered automatically from a real
deadlock with zero code changes; verification was thorough (13/13 tasks,
207/207 blocking DQ, 8/8 freshness); the incident was resolved through the
formal alert-resolution contract; and the team followed the runbook by
capturing evidence first and deferring any concurrency change to a measured
follow-up (PART 13) rather than tuning under pressure.

**What was lucky / needs attention:** the deadlock's loser backend was
aborted by PostgreSQL and the retry simply did not hit the same lock cycle —
that is timing luck, not a guarantee. Deadlocks of this class remain
possible; the accepted position (from the PART 13 evidence) is deliberately
narrow: the two-thread default retained measured throughput and one validated
production run completed without a lock incident, not that deadlocks are
impossible. Luck was converted into durable controls — lower default
concurrency, lock logging, statement statistics, and permanent lock drills —
so the next occurrence is detected with evidence rather than survived by
chance. This incident also complements the controlled
[lock contention drill](../postmortems/2026-09_postgres_lock_contention.md):
the drill proves the diagnostics layer detects lock blocking, while this
incident proves the orchestration layer recovers from a real one.
