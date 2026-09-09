# PART 9 — Incremental Processing Contract

## Scope

PART 9 converts the high-volume operational facts from full table rebuilds to
idempotent dbt incremental models. The closed staging, identity, intermediate,
and star-schema grains are preserved.

Incremental facts:

- `fact_orders` — unique key `order_key`
- `fact_order_items` — unique key `order_item_key`
- `fact_shop_daily` — unique key `date_key`
- `fact_campaign_daily` — unique key `date_key`
- `fact_live_daily` — unique key `date_key`
- `fact_product_card_daily` — unique key `date_key`
- `fact_influencer_observation` — unique key `influencer_observation_key`

Dimensions remain table materializations because they are small current-state
Type-1 dimensions. `dim_date` also remains a full calendar rebuild.

## PostgreSQL Strategy

All seven facts use dbt `incremental` materialization with PostgreSQL
`delete+insert`, an explicit `unique_key`, and `on_schema_change='fail'`.
This keeps replacement deterministic at the declared fact grain and prevents
silent target-schema drift.

## Watermark and Lookback

Normal runs derive state from the target table rather than creating a second
state store. The source predicate is:

`source_watermark >= max(target_watermark) - 24 hours`

The 24-hour lookback intentionally reprocesses recent keys. Reprocessing is
safe because `unique_key` replacement is idempotent.

Late-arriving business records are captured because raw `_ingested_at` reflects
when the observation entered the platform, even when its business date is old.

## Explicit Backfill

`backfill_start` is inclusive and `backfill_end` is exclusive. When both vars
are provided on an existing incremental relation, the watermark predicate is
replaced by a business-date predicate for that window.

Order facts backfill by `created_at::date`; daily facts by `metric_date`; and
influencer observations by `ingested_at::date`.

The vars must be supplied together. A partial pair raises a compiler error.
During `--full-refresh`, `is_incremental()` is false, so backfill vars do not
restrict the rebuild; the full dataset is rebuilt.

## Order Aggregation Safety

`fact_orders` first identifies changed order IDs, then recomputes each changed
order from all current SKU lines. A change to one SKU line therefore cannot
produce a partial order-level aggregate.

## Deletion Boundary

Raw ingestion is append-oriented. PART 9 does not invent hard-delete or
tombstone semantics that are absent from the source contracts. If a business
source later supplies explicit deletion events, that requires a separate
contract and downstream propagation policy.

## Operational Selector

`incremental_facts` selects exactly the seven incremental facts. Normal dbt
operations can therefore run the fact layer without enumerating model names.

## PART 10 Handoff

Airflow may safely invoke the normal incremental selector repeatedly. For a
scheduled data interval or operator-requested reprocessing window, Airflow can
pass `backfill_start` and `backfill_end`. The dbt contract remains responsible
for idempotent key replacement; Airflow remains responsible for scheduling,
retries, task timeouts, concurrency, and operational visibility.
