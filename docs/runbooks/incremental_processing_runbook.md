# Incremental Processing Runbook

## Normal Operation

From the `dbt` directory:

```bash
dbt run --profiles-dir . --selector incremental_facts
```

Normal runs use the maximum target watermark minus the configured 24-hour
lookback. Recent keys may be processed again; unique-key replacement makes this
safe and idempotent.

Run blocking quality gates after transformation:

```bash
dbt test --profiles-dir . --selector dq_blocking
```

Warnings are operational signals and may be reviewed separately:

```bash
dbt test --profiles-dir . --selector dq_warning
```

## Date-Window Backfill

Use an inclusive start and exclusive end:

```bash
dbt run --profiles-dir . --selector incremental_facts \
  --vars "{backfill_start: '2026-08-15', backfill_end: '2026-08-16'}"
```

Backfill dates map to model business grain:

- orders/order items: created date
- daily facts: metric date
- influencer observations: ingestion/observation date

Always provide both boundaries. A partial pair is a compiler error.

## Full Rebuild

Use full refresh only when the incremental target requires complete recovery or
a controlled schema/data rebuild:

```bash
dbt run --profiles-dir . --full-refresh --selector incremental_facts
```

Backfill vars do not restrict full refresh.

## Troubleshooting

If a late-arriving record is missing, check its source `_ingested_at`, the target
maximum watermark, and the configured lookback. If the source observation is
older than the watermark window, run an explicit date backfill.

If `on_schema_change='fail'` stops a model, do not bypass the failure. Compare
the model contract and target table schema, determine whether the change is
intentional, then use a reviewed full refresh or migration.

Hard deletes are not propagated because current source contracts are
append-oriented. Do not manually infer tombstones from missing files or rows.
