# Intermediate Transformation Runbook

## Purpose

Build and validate PART 6 current-state and enrichment models without changing raw or staging data.

## Run

```powershell
dbt run --project-dir dbt --profiles-dir dbt --target dev --select path:models/intermediate
dbt test --project-dir dbt --profiles-dir dbt --target dev --select path:models/intermediate
```

## Expected schemas

- input: `analytics_staging`, `analytics_identity`
- output: `analytics_intermediate`

## First checks after a failure

1. Check dbt compilation output.
2. Check business-key multiplicity in staging.
3. Check whether the join is LEFT JOIN and row preserving.
4. Check `ingested_at`, pipeline run, ingestion file, and row-id ordering.
## Interpretation

- `source_observation_count > 1` is expected when snapshots or overlapping exports repeat a business key.
- `unmatched_sku` must not remove an Order-SKU row.
- `unmatched_influencer_entity` is expected when creator handles have no conservative roster match.
- `metric_date IS NULL` remains visible in staging but is excluded from date-grain intermediate models.

## Do not

- do not delete repeated raw/staging rows
- do not use follower, budget, or engagement values as identity join keys
- do not convert LEFT JOIN enrichment to INNER JOIN to make unmatched counts disappear
- do not treat the technical MD5 key as anonymization
