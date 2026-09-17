# Postmortem Template (Blameless)

Use one file per incident in `docs/postmortems/`, named
`YYYY-MM_short_slug.md`. Keep it factual; separate what we know from what we
believe. Write it within a few days of resolution while evidence is fresh.

---

# Postmortem: <short incident title>

| Field | Value |
| --- | --- |
| Incident date | YYYY-MM-DD |
| Severity | SEV1 / SEV2 / SEV3 / SEV4 |
| Status | Resolved / Monitoring / Open |
| Detected at | <timestamp + how: alert, DagRun failure, KPI report, manual> |
| Resolved at | <timestamp> |
| Time to recover | <duration; compare against the KPI MTTR baseline> |
| Author | <name/role> |
| Related alert IDs | `audit.pipeline_alerts` IDs, if any |
| Evidence | <links: monitoring snapshot, drill output, commits, logs> |

## Summary

Two or three sentences: what happened, what the impact was, and what the
single root cause was.

## Impact

- Which pipelines / tables / marts / consumers were affected and for how long.
- Data consequences: was any data lost, corrupted, duplicated, or merely late?
- What users or downstream systems actually experienced (not what we feared).

## Timeline (all times <timezone>)

| Time | Event |
| --- | --- |
| HH:MM | <trigger / change that started it> |
| HH:MM | <detection: alert fired / run failed / someone noticed> |
| HH:MM | <triage findings> |
| HH:MM | <containment action> |
| HH:MM | <resolution action> |
| HH:MM | <verification that recovery is real> |

## Root cause

The fixable condition that made this incident possible. Keep asking "why"
until the answer is something that can be changed (code, config, process,
missing guardrail) — not "a task failed".

## What went well

- Detection/containment/recovery steps that worked as designed.
- Existing guardrails that limited the blast radius.

## What went poorly / gaps

- Where detection was slow, noisy, or missing.
- Where the runbook was wrong, incomplete, or did not exist.
- Assumptions that turned out to be false.

## Action items

| # | Action | Owner | Due | Verification |
| --- | --- | --- | --- | --- |
| 1 | <specific, fixable change> | <owner> | <date> | <how we will know it is done> |

## Lessons learned

What we now know about the system that we did not know before, and what
future designs should assume because of it.

## References

- Runbooks, drill docs, monitoring queries, commit SHAs, dashboards.
