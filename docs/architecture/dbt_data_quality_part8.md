# PART 8 - dbt Data Quality and Testing Hardening

## Purpose

PART 8 adds an explicit dbt quality policy on top of the existing structural,
identity, reconciliation, and warehouse tests. It does not change raw,
staging, intermediate, identity, or star-schema grain.

## Severity Policy

Blocking tests use `severity: error` and tag `dq_blocking`. They protect
impossible states and warehouse consistency, including negative measures and
order-to-item rollup reconciliation.

Observable tests use `severity: warn` and tag `dq_warning`. They surface
anomalies that require review but should not automatically stop the pipeline,
including safe-cast nulls, rate-range anomalies, chronology anomalies, and
unknown dimension usage.

## Freshness Policy

Raw source freshness uses `_ingested_at` as the loaded-at timestamp. Incremental
operational sources warn after 48 hours. Snapshot sources warn after 7 days.
No freshness error threshold is defined because the project does not yet have
a business-approved arrival SLA.

## Privacy Boundary

Tests do not use `store_failures`. Failing private business/order rows are not
materialized into additional dbt failure tables. Public evidence contains only
aggregate counts and synthetic validation outcomes.
