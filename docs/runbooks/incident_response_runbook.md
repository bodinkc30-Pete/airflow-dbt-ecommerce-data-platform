# Incident Response & Postmortem Runbook

## Purpose

Define how pipeline incidents are classified, worked, resolved, and learned
from. This runbook covers detection through postmortem; the failure-injection
drills in `failure_injection_runbook.md` are how we rehearse it.

## Severity classification

Severity is set by **user/business impact and blast radius**, not by how loud
the alert is. The pipeline's alert severities (`audit.pipeline_alerts.severity`)
map to incident severities as follows:

| SEV | Pipeline signal | Impact | Examples in this platform |
| --- | --- | --- | --- |
| SEV1 | `critical` alert(s), pipeline failure blocking all delivery | Data platform down or data loss; downstream consumers blocked | DagRun failed with no successful retry; restore drill `verification_status = failed` on a real incident; PII exposure to a public layer |
| SEV2 | `error` alert(s); partial failure | One pipeline path down or degraded; stale data for some consumers | `pipeline_failure` alert with blocked tasks; schema drift stopping ingestion; backup drill failing repeatedly |
| SEV3 | `warning` alert(s) | Degraded but functioning; data late or quality reduced | `slow_pipeline` (duration over threshold); dbt freshness warnings; data-quality warnings |
| SEV4 | No alert; found by inspection | Minimal impact; cosmetic or tooling issue | Broken doc link; noisy log line; non-prod test flake |

If two severity candidates apply, take the higher one until impact is proven
otherwise.

## Incident lifecycle

```text
DETECT -> TRIAGE -> CONTAIN -> RESOLVE -> POSTMORTEM -> FOLLOW-UP
```

1. **DETECT** — an alert from `audit.pipeline_alerts` / the monitoring task, a
   failed DagRun, a KPI anomaly from `report_reliability_kpi.py`, or a manual
   observation. Record when and how it was detected; alert latency is a
   postmortem data point.
2. **TRIAGE** — classify severity (table above), identify blast radius (which
   sources/marts/consumers are affected), and decide whether to page. Check
   the monitoring snapshot (`audit.pipeline_monitoring_runs`) and recent
   alerts before touching anything.
3. **CONTAIN** — stop the bleeding with the smallest reversible action: pause
   the DAG, cancel a single runaway backend (never blindly terminate
   sessions), reject a bad file at the ingestion boundary, disable a failing
   integration. Containment is not a fix; note it explicitly as temporary.
4. **RESOLVE** — apply the real fix, recover the pipeline, and VERIFY: the
   failing condition is gone *and* the affected operation completes cleanly
   (a passing retry alone is not recovery evidence). Update the alert row:
   `resolved = TRUE`, `resolved_at`, root cause, remediation, recovery
   reference (`resolved_by_dag_run_id` where applicable).
5. **POSTMORTEM** — for every SEV1/SEV2 (and any SEV3 with real consumer
   impact), write a blameless postmortem from `docs/templates/postmortem_template.md`
   within a few days, while facts are fresh. See `docs/postmortems/`.
6. **FOLLOW-UP** — file and track every action item from the postmortem. An
   incident is not closed until its action items are done or explicitly
   accepted as wont-fix.

## On-call / response expectations

| Severity | Acknowledge | Contain | Status updates |
| --- | --- | --- | --- |
| SEV1 | Immediately | Before anything else | Every 30 min until resolved |
| SEV2 | Same business day | Same day | Daily until resolved |
| SEV3 | Within 2 business days | Next scheduled run may proceed if risk accepted | In the postmortem/notes |
| SEV4 | Best effort | Not required | None required |

Always: work from evidence (monitoring snapshots, logs, drill output), prefer
reversible actions, and never trade data integrity for a green run.

## Postmortem principles

- **Blameless**: failures come from systems and assumptions, not from people
  being careless. Name mechanisms, not individuals.
- **Timeline-first**: reconstruct what happened, in order, with timestamps;
  separate facts from hypotheses.
- **Root cause over proximate cause**: keep asking why until the answer is a
  fixable condition, not "a query was slow".
- **Action items are the deliverable**: each item has an owner, a deadline,
  and a verification method.
- **Evidence-backed**: link the alert rows, monitoring snapshots, drill
  evidence, and commits that the claims rely on.

## Reference implementation

`docs/postmortems/2026-09_postgres_lock_contention.md` is the filled example:
an advisory-lock failure-injection drill worked through the full lifecycle,
including what the drill proved and what it deliberately did not prove.
