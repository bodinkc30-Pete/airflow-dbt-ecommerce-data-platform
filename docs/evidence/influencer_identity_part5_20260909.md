# PART 5 — Influencer Identity Runtime Evidence

Date: 2026-09-09

## Implemented boundary

- Input: `analytics_staging.stg_influencer`
- Row-preserving map: `analytics_identity.influencer_identity_map`
- Entity registry: `analytics_identity.influencer_entities`
- Review queue: `analytics_identity.influencer_identity_review_queue`
- Identity method: `normalized_name_v1`
- Confidence: `provisional`

## Current PostgreSQL runtime

- staging rows: 10
- mapped rows: 10
- entity rows: 5
- distinct normalized names: 5
- reconciled source rows: 10
- review rows: 4
- null entity keys: 0
- invalid key format rows: 0
- false cross-snapshot review flags: 0

These database rows are synthetic/runtime-validation data, not committed private business data.

## Private source dry run

Read-only profiling of the private normalized source produced:
- usable rows: 92
- provisional entities: 88
- deterministic entity keys: 88
- duplicate normalized keys: 4
- review candidates: 4
- extra merges introduced by normalization: 0
- null entity keys: 0
- database writes: none

No creator names, source paths, or business values are recorded in this evidence file.

## Validation

- dbt compile: PASS
- dbt build: 78/78 PASS
- dbt data tests: 67/67 PASS
- Python compile: PASS
- Ruff: PASS
- pytest regression: 281 passed
- Airflow DAG import errors: none
