# Source Contract 05 - TikTok Product Card Traffic

## Source Identity

- Source ID: `SRC_PRODUCT_CARD_TRAFFIC`
- Domain: Product Traffic / Conversion
- Source system: TikTok Seller / Product Analytics
- Source format: Excel export
- Target raw table: `raw_product_card_daily`
- Classification: Private business data

## Grain

One row represents one product-card performance day in the normalized daily layer.

If the source contains product-level identifiers, the preferred detailed grain is:

`product_id + metric_date`

If SKU-level identifiers are available, the pipeline may preserve:

`sku_id + metric_date`

before aggregation.

## Business Key

Preferred business identity:

`product_id + metric_date`

When a stable product identifier is unavailable, the pipeline must derive and
document a surrogate identity from available product attributes.

## Multi-File Ingestion

This source may arrive as multiple exports covering different reporting periods.

All valid files must be normalized into the same raw table:

`raw_product_card_daily`

The pipeline must preserve source-file lineage for every record.

## Load Strategy

- Incremental ingestion by metric date
- Multi-file ingestion
- Idempotent reruns
- UPSERT support for corrected historical metrics
- Late-arriving corrections supported
- File-level duplicate detection using file hash
- Overlapping reporting windows must be handled safely

## Core Metrics

The source may contain metrics including:

- Product card views
- Product card clicks
- Customers
- SKU orders
- Product card GMV
- Content-attributed GMV
- Click-through metrics
- Add-to-cart metrics
- Checkout metrics
- Payment metrics
- Conversion-rate metrics

## Data Quality Requirements

The ingestion pipeline must validate:

- Source file exists
- Source file is not empty
- Required reporting date exists
- Reporting date is parseable
- Product or SKU identity is valid when present
- View metrics are numeric and non-negative
- Click metrics are numeric and non-negative
- Order metrics are numeric and non-negative
- GMV fields are numeric
- Duplicate product-day records are detectable
- Overlapping files do not create duplicate final records
- Unexpected schema drift stops ingestion

## Known Real-World Characteristics

The source contains characteristics that the pipeline must handle:

- Multiple monthly or partial-month export files
- Overlapping reporting periods
- Different activity levels by date
- Days with traffic but no orders
- Days with orders but low traffic
- Historical corrections
- Conversion metrics whose business definitions require interpretation
- Metrics that may exceed intuitive percentage bounds because of attribution
  or reporting semantics

## Conversion Metric Policy

Conversion-related metrics must not automatically be rejected only because a
reported percentage exceeds 100 percent.

Such records should be classified as warnings unless the source definition
explicitly proves the value is invalid.

The pipeline should record:

- metric name
- metric value
- reporting date
- source file
- quality severity
- investigation status

## Derived Metrics

The downstream transformation layer may calculate:

- click_through_rate = clicks / views
- orders_per_click = orders / clicks
- gmv_per_click = gmv / clicks
- gmv_per_order = gmv / orders
- customers_per_click = customers / clicks

Derived metrics must safely handle zero denominators.

## Reconciliation Role

Product Card Traffic may be reconciled against:

- Product performance
- SKU performance
- Shop Analytics
- Order transactions
- Campaign performance

Traffic-attributed or content-attributed GMV must not automatically be expected
to equal total shop GMV.

## Privacy Classification

This source is primarily aggregate product performance data.

Customer-level PII should not be required for downstream analytics.

Any unexpected personal information must remain in the private layer.

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

`raw_product_card_daily`
-> `stg_product_card_daily`
-> `int_product_performance`
-> `fct_product_card_daily`

The product-card fact model will support traffic, conversion, and product
performance analysis.

## Failure Policy

Critical failures include:

- unreadable source file
- missing reporting date
- invalid required identifiers
- invalid required numeric values
- incompatible schema drift
- duplicate records that violate the defined grain after normalization

Non-critical anomalies should be logged for downstream quality evaluation.

## Public Portfolio Policy

The original private Product Card Traffic exports must not be committed to Git.

Public demonstrations and CI must use portfolio-safe data preserving the same
multi-file ingestion behavior, overlapping windows, traffic patterns, and data
quality scenarios without exposing private business information.