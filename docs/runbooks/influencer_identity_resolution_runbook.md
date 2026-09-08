# Influencer Identity Resolution Runbook

## Build and validate

From the repository root:

```powershell
dbt run --project-dir dbt --profiles-dir dbt --target dev --select path:models/identity
dbt test --project-dir dbt --profiles-dir dbt --target dev
```

Expected output schema: `analytics_identity`.

## Reconciliation checks

Verify that:
- identity-map row count equals `stg_influencer` row count;
- entity count equals distinct normalized names;
- sum of entity `source_row_count` equals identity-map row count;
- entity keys are non-null and unique;
- every mapped entity key exists in the entity registry.

The committed dbt tests enforce these invariants.

## Review queue

Inspect `analytics_identity.influencer_identity_review_queue` only in the private environment.
Do not export real creator names or source payloads into CI, screenshots, or the public portfolio.

For a flagged entity:
1. confirm whether duplicate observations occur in the same ingestion file;
2. compare identity evidence, not changing metrics, before deciding that two rows are different people;
3. never delete or rewrite raw/staging rows to resolve an identity issue;
4. record future stronger identity evidence through a versioned resolution method.

Follower, engagement, and budget changes across different snapshots are not identity conflicts.

## Escalation

If a verified platform creator ID or handle becomes available, stop before changing existing entity keys.
Create a new identity-method version and run explicit reconciliation tests first.
