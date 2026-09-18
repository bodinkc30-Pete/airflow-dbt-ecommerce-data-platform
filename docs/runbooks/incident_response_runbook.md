# Incident Response Runbook

## Purpose

This runbook defines how on-call engineers classify, acknowledge, investigate,
mitigate, recover, verify, and resolve incidents for the ecommerce data
platform (Airflow ingestion DAG, PostgreSQL, dbt transformations, and the
monitoring/alert control plane).

It connects the human on-call process to the tooling that already exists in
this repository. It does not introduce a new alerting system; it operates the
one defined by `database/schema/10_create_pipeline_monitoring.sql` and
`database/schema/11_harden_pipeline_alert_incidents.sql`.

Related runbooks:

- [PostgreSQL Production Diagnostics Runbook](postgres_operations_runbook.md)
- [Reliability Incident Runbook](reliability_incident_runbook.md)
- [Monitoring and Alerting Runbook](monitoring_alerting_runbook.md)
- [Failure Injection Runbook](failure_injection_runbook.md)
- [Postmortem Template](../templates/postmortem_template.md)

## Severity classification

Classify an incident by user and decision impact, not by how alarming the
error message looks. Record the SEV level in the incident notes and adjust it
as evidence arrives.

| Severity | Definition | Examples in this platform |
| --- | --- | --- |
| SEV1 | Pipeline or critical data is unavailable. All stakeholders are blocked; no current data is usable for decisions. | `ecommerce_ingestion` DagRuns failing repeatedly with `pipeline_failure` alerts and no successful recovery run; PostgreSQL unreachable so no ingestion, transformation, or diagnostics can run. |
| SEV2 | Major degradation. Some consumers are blocked, or data is materially late beyond the expected delivery window. | One layer (for example dbt marts) failing while raw ingestion continues; a `slow_pipeline` alert where duration far exceeds recent successful runs; recurring lock contention blocking a critical task. |
| SEV3 | Limited impact. A workaround exists and primary decision-making is not affected. | A single non-blocking `data_quality_warning` or `dbt_warning`; one source file rejected while all other files load. |
| SEV4 | Investigation or early warning. No user impact yet. | A first-time `dbt_freshness_warning`; a warning-severity alert with green DagRuns; anomalies found by a scheduled failure drill. |

Mapping note: the alert table constraint
(`chk_pipeline_alert_severity` in
`database/schema/10_create_pipeline_monitoring.sql`) allows `warning`,
`error`, and `critical`. SEV is a human incident classification layered on top
of those alert severities; a `critical` alert is normally SEV1/SEV2, an
`error` alert is normally SEV2/SEV3, and a `warning` alert is normally
SEV3/SEV4. Evidence can always move an incident up or down.

## Incident lifecycle

```text
Detected -> Acknowledged -> Investigating -> Mitigated -> Recovered -> Verified -> Resolved
```

| State | Entry condition | Exit condition |
| --- | --- | --- |
| Detected | A monitoring alert row appears in `audit.pipeline_alerts` / `audit.open_pipeline_alerts`, an Airflow DagRun fails, a webhook notification is delivered, or a human reports bad data. | On-call has seen the alert and taken ownership. |
| Acknowledged | The on-call engineer confirms receipt, notes the alert ID / DagRun ID, and starts a timeline. | Severity is classified and the investigation has a named owner. |
| Investigating | Owner runs read-only diagnostics (see below) and correlates PostgreSQL state, Airflow task logs, monitoring rows, and recent changes. | Root cause is identified well enough to pick a safe mitigation, or the incident is escalated. |
| Mitigated | The immediate user impact is stopped (blocking cleared, bad source quarantined, rerun in progress). Impact may be reduced, not yet eliminated. | The affected operation can complete end to end. |
| Recovered | A recovery DagRun or equivalent operation completes successfully. | Verification evidence is gathered; recovery alone is not closure. |
| Verified | The verification gate chain passes: Airflow task/DagRun state green, blocking dbt DQ green, row-count/reconciliation checks pass, `audit.pipeline_health_latest` healthy, and no synthetic residue from any probe or drill. | Evidence is recorded in the incident record. |
| Resolved | The alert is resolved through the incident-resolution contract with root-cause category, root-cause summary, remediation summary, recovery DagRun ID, and verification summary (see `resolve_pipeline_alert()` in `src/ecommerce_pipeline/reliability/incident_diagnostics.py`). For SEV1/SEV2 a postmortem is opened using the [Postmortem Template](../templates/postmortem_template.md). | Incident closed; corrective actions tracked. |

Never skip from Recovered directly to Resolved. A started retry is not
recovery, and a green retry is not verification.

## On-call expectations

- Acknowledge within 15 minutes for SEV1/SEV2 alerts and within one business
  hour for SEV3/SEV4. These are project targets, not measured SLAs.
- Keep an incident timeline from first detection: timestamps, commands run,
  evidence observed, decisions made.
- Never change production data, schema, transaction ownership, retry policy,
  or Airflow configuration from symptoms alone. Every change must be backed
  by captured evidence (diagnostics snapshot, task log, alert row).
- Prefer read-only tooling first. Both diagnostics CLIs open
  `readonly=True, autocommit=True` sessions and cannot mutate state.
- Do not terminate or cancel arbitrary PostgreSQL sessions. The failure
  drills in `tests/failure/` only ever act on PIDs and advisory locks they
  created themselves; apply the same discipline to real incidents.
- Escalate when: root cause is unclear after initial triage, the incident is
  SEV1 for more than 30 minutes without mitigation, the same failure recurs,
  or the required fix crosses a boundary the runbooks forbid (for example
  transaction ownership or concurrency changes, which belong to
  evidence-driven performance analysis).
- If delivery of external notifications failed (`delivery_status = failed` or
  `not_configured`), treat the missing page as part of the incident and check
  `audit.open_pipeline_alerts` directly; a silent webhook must never hide an
  open alert.

## Tooling map

| Need | Tool |
| --- | --- |
| Airflow + pipeline run triage | `python scripts/diagnose_pipeline_run.py --dag-run-id <run-id>` (add `--json` for machine-readable output) |
| PostgreSQL health snapshot | `python scripts/diagnose_postgres.py` (`--long-running-seconds`, `--top-queries`, `--json`) |
| Direct SQL triage | `sql/operations/postgres_diagnostics.sql` |
| Latest pipeline health | `audit.pipeline_health_latest` view |
| Open alerts | `audit.open_pipeline_alerts` view |
| Per-run telemetry | `audit.pipeline_monitoring_runs` table |
| Alert resolution contract | `resolve_pipeline_alert()` in `src/ecommerce_pipeline/reliability/incident_diagnostics.py`, enforced by `chk_pipeline_alert_resolution_contract` in `database/schema/11_harden_pipeline_alert_incidents.sql` |
| Controlled failure drills | `tests/failure/` with the [Failure Injection Runbook](failure_injection_runbook.md) |

## "The system is down at night" — step-by-step response

This is the canonical interview answer and the real operating procedure.

1. **Detect and acknowledge.** The monitoring layer records the failed or
   slow run and raises an alert (`pipeline_failure`, `slow_pipeline`, and
   related types). Acknowledge the alert, note the `pipeline_alert_id` and
   `dag_run_id`, and start the timeline. If no alert fired, that itself is
   incident evidence.
2. **Classify severity.** Decide SEV1–SEV4 based on stakeholder impact: is
   all data unavailable, partially degraded, or merely a warning? A nightly
   batch failure with no consumers until morning is usually SEV2, not SEV1.
3. **Diagnose read-only, nothing else.** Run
   `python scripts/diagnose_pipeline_run.py --dag-run-id <run-id>` to see
   DagRun state, task attempts, monitoring status, and alerts. Run
   `python scripts/diagnose_postgres.py` to check connection pressure,
   blocking sessions, and long-running transactions. Query
   `audit.pipeline_health_latest` and `audit.open_pipeline_alerts`. Read the
   failing Airflow task log to find the first actionable error.
4. **Classify root cause** using the supported categories
   (`transient_dependency`, `database`, `data_quality`, `schema`,
   `transformation`, `orchestration`, `timeout`, `resource`, `configuration`,
   `unknown`) from `database/schema/11_harden_pipeline_alert_incidents.sql`.
5. **Mitigate with the narrowest safe action.** Allow the configured retry
   for transient failures, quarantine only the offending data lineage for bad
   rows, or rerun the failed model. Do not hot-fix code on production in the
   middle of the night without evidence.
6. **Recover and verify.** Confirm the recovery DagRun succeeds, then run the
   verification chain: task/DagRun state, blocking dbt DQ, row-count and
   reconciliation checks, latest monitoring health, and residue checks for
   any probe used.
7. **Resolve with evidence.** Resolve the alert through
   `resolve_pipeline_alert()` so the record carries root cause, remediation,
   recovery DagRun ID, and verification summary. The database constraint
   rejects resolution without all four fields.
8. **Follow up in daylight.** For SEV1/SEV2, write the postmortem from the
   [Postmortem Template](../templates/postmortem_template.md), add corrective
   actions with owners and due dates, and add a regression test or failure
   drill so the same incident is caught earlier next time.
