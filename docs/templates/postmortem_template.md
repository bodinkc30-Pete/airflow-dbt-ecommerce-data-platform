# Postmortem Template

> Blameless culture note: postmortems in this project analyze systems,
> timing, and assumptions — never individuals. Name components, queries,
> thresholds, and runbooks, not people. If a human action contributed, describe
> the condition that made the action reasonable at the time. The goal is a
> system that makes the right action easy and the wrong action hard.
>
> Use this template for every SEV1 and SEV2 incident, and for SEV3/SEV4 when
> there is a reusable lesson. Delete guidance blocks (the italic lines under
> each heading) before publishing. Severity levels are defined in the
> [Incident Response Runbook](../runbooks/incident_response_runbook.md).
> A filled example lives at
> [2026-09 PostgreSQL Lock Contention](../postmortems/2026-09_postgres_lock_contention.md).

## Summary

*Two to four sentences: what happened, what the impact was, how it was
resolved, and the single most important takeaway. A reader should understand
the incident from this section alone.*

## Impact

*Who and what was affected: stakeholders, DAGs, tables, models, downstream
consumers. Quantify where evidence exists (rows delayed, runs failed, duration
overrun). State explicitly when there was no production impact, for example
for controlled drills.*

## Severity

*SEV1–SEV4 per the [Incident Response Runbook](../runbooks/incident_response_runbook.md),
with a one-line justification. Note whether severity changed during the
incident and why.*

## Timeline

*All times in a stated timezone. Be honest about gaps; a missing timestamp is
better than an invented one. Use "T+" offsets when only relative durations are
known from test or log evidence.*

| Time | Event |
| --- | --- |
| YYYY-MM-DD HH:MM TZ | Incident detected (how) |
| ... | ... |

## Detection

*Who or what detected the incident: monitoring alert type from
`audit.pipeline_alerts`, Airflow task failure, human report, or failure drill.
Did existing monitoring catch it? If a human found it first, say so — that is
a monitoring gap to fix, not a blame item.*

## Root Cause

*The mechanism that caused the incident, stated at the level of evidence:
query, lock type, threshold, configuration value. Use one of the project
root-cause categories (`transient_dependency`, `database`, `data_quality`,
`schema`, `transformation`, `orchestration`, `timeout`, `resource`,
`configuration`, `unknown`) from
`database/schema/11_harden_pipeline_alert_incidents.sql`.*

## Contributing Factors

*Conditions that made the incident possible or worse but were not the root
cause: missing test coverage, threshold sizing, environment parity gaps,
documentation gaps.*

## Mitigation

*The immediate action that stopped user impact, and why it was the narrowest
safe action.*

## Recovery

*How full service was restored: recovery DagRun ID, retries, quarantine and
rebuild, or drill cleanup. Link the recovery run so the incident record can
connect failure to verified recovery.*

## Verification

*Evidence that recovery is real, not just a started retry: DagRun state,
blocking dbt DQ results, row-count/reconciliation checks,
`audit.pipeline_health_latest` state, residue checks for any injected state.
Include test counts and durations where they exist.*

## Why Monitoring Did or Did Not Catch It

*If monitoring caught it: which signal, how fast, and was it fast enough? If
not: what signal was missing, and which corrective action adds it?*

## Corrective Actions

*Concrete, owned, dated actions. Each must be verifiable. Avoid "be more
careful" actions.*

| Action | Owner | Due date |
| --- | --- | --- |
| | | |

## Regression Prevention

*The specific test, drill, or CI gate that prevents recurrence. Reference
existing suites where possible (`tests/failure/`, Quality Gate, PostgreSQL
integration job) and describe what is added.*

## Lessons Learned

*What the team now knows that it did not before. Separate "what went well"
(fast detection, clean recovery) from "what was lucky" (retry happened to
succeed) — luck is a corrective action in disguise.*
