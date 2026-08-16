# Source Contract 02 - TikTok Shop Analytics

## Source Identity

- Source ID: `SRC_SHOP_ANALYTICS`
- Domain: Shop Performance
- Source system: TikTok Seller
- Source format: Excel export
- Target raw table: `raw_shop_daily`
- Classification: Private business data

## Grain

One row represents one shop-day.

The source contains daily shop-level performance metrics.

## Business Key

Primary business identity:

`metric_date`

Each date should represent one daily shop performance record after
normalization.

## Load Strategy

- Incremental ingestion by metric date
- Idempotent reruns
- UPSERT support for corrected historical metrics
- Late-arriving corrections supported
- File-level duplicate detection using file hash

## Core Metrics

The source may contain metrics including:

- GMV
- Orders
- Customers
- Items sold
- Refunded items
- SKU orders
- Gross revenue
- Page views
- Visitors
- Conversion-related metrics
- Average order value
- LIVE-attributed GMV
- Affiliate/video-attributed GMV

## Data Quality Requirements

The ingestion pipeline must validate:

- Source file exists
- Source file is not empty
- Required date column exists
- Metric date is parseable
- Metric date is not null
- Daily grain is preserved
- Numeric fields are parseable
- Currency values are non-negative unless business semantics allow otherwise
- Duplicate daily rows are detectable
- Unexpected schema drift stops ingestion
- Historical corrections are traceable

## Known Real-World Characteristics

The source contains characteristics that the pipeline must handle:

- Daily time-series data
- Large differences between activity levels across dates
- Multiple revenue attribution metrics
- Historical comparison periods
- Corrected or refreshed historical values
- Metrics that may be zero on inactive days
- Different reporting windows between exports

## Reconciliation Role

Shop Analytics is a primary reconciliation source for comparison against:

- Order-level transactions
- Product performance reports
- SKU performance reports
- Campaign performance reports
- LIVE performance reports

Differences between sources must not automatically be treated as failures.

The pipeline should support reconciliation tolerances and record:

- absolute difference
- percentage difference
- comparison window
- source pair
- reconciliation status

## Privacy Classification

This source is primarily aggregate business data.

It does not normally require buyer-level PII for downstream analytics.

Any unexpected personal information found during ingestion must remain in the
private layer and must not be published downstream.

## Raw Lineage Metadata

The pipeline adds:

- `_source_file`
- `_source_row_number`
- `_batch_id`
- `_file_hash`
- `_ingested_at`
- `_pipeline_run_id`

## Downstream Models

Planned downstream flow:

`raw_shop_daily`
-> `stg_shop_daily`
-> `int_daily_sales`
-> `fct_daily_sales`

Shop Analytics will also contribute to cross-source reconciliation models.

## Failure Policy

Critical failures include:

- unreadable source file
- missing required date field
- invalid required date values
- incompatible schema drift
- duplicate records that violate daily grain

Non-critical anomalies should be logged for downstream quality evaluation.

## Public Portfolio Policy

The original business export must not be committed to Git.

Public demonstrations and CI must use a portfolio-safe dataset preserving
the same daily grain, schema behavior, and reconciliation scenarios without
exposing private business information.