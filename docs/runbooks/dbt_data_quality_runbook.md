# dbt Data Quality Runbook

## Blocking Checks

Run:

`dbt test --selector dq_blocking`

Any failure blocks promotion of the transformed data. Investigate the compiled
test SQL, identify the affected model and business rule, then trace the row
through intermediate, staging, and raw lineage. Do not repair raw source truth
in place.

## Warning Checks

Run:

`dbt test --selector dq_warning`

Warnings are operational review signals. They do not automatically stop the
pipeline. Review cast-null, rate-range, chronology, and unknown-dimension
warnings separately and decide whether the upstream source, parsing contract,
or business rule needs change.

## Source Freshness

Run:

`dbt source freshness`

Incremental sources warn after 48 hours and snapshot sources warn after 7 days.
A warning means the latest ingestion timestamp exceeded the engineering default;
it is not yet a contractual source SLA.
