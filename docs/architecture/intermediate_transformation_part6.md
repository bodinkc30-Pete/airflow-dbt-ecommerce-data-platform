# PART 6 — Intermediate Transformation Architecture

## Purpose

The intermediate layer converts typed staging observations into reusable business-ready relations without creating warehouse facts or dimensions.

Output schema: `analytics_intermediate`
Materialization: dbt views

## Current-state policy

Snapshot and repeatable business keys are consolidated with deterministic latest-observation ordering:

1. business key
2. `ingested_at DESC`
3. `pipeline_run_id DESC`
4. `ingestion_file_id DESC`
5. raw/staging row id DESC

This prevents many-to-many multiplication when snapshots or overlapping exports accumulate.
## Business grains

- `int_products_current`: one row per `product_id`
- `int_skus_current`: one row per `sku_id`
- `int_product_sku_catalog`: one row per current `sku_id`
- `int_order_items_current`: one row per `(order_id, sku_id)`
- `int_creator_identity_bridge`: one row per normalized nonblank creator handle
- `int_order_items_enriched`: one row per current order-SKU key
- source-specific daily current models: one row per valid `metric_date`
- `int_daily_performance`: one row per date observed by at least one daily source

## Join policy

Catalog and identity enrichment use LEFT JOINs. Unmatched references are preserved and labeled instead of being discarded.

Creator-to-influencer matching reuses conservative `normalized_name_v1` normalization. No fuzzy matching, punctuation stripping, follower metrics, budget, or engagement metrics are used for identity joins.
## Business keys and safety

`order_item_key` is versioned and deterministic from `(order_id, sku_id)`. The MD5 digest is a compact technical key only; it is not anonymization or a security control.

Malformed dates remain preserved in staging as NULL typed dates. Date-grain intermediate models exclude NULL dates, and reconciliation tests prove that every valid distinct date is represented exactly once.

## Boundaries

PART 6 does not create facts, dimensions, SCD logic, incremental dbt materializations, or Airflow dbt orchestration. Those remain later project parts.

Private business data is used only for local read-only profiling. No raw values, creator names, identifiers, or private file paths are committed.
