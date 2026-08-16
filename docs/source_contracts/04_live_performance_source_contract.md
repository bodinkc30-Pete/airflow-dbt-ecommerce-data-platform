# Source Contract 04 - TikTok LIVE Performance

## Source Identity

- Source ID: `SRC_LIVE_PERFORMANCE`
- Domain: LIVE Commerce
- Source system: TikTok Seller / LIVE Analytics
- Source format: Excel export
- Target raw table: `raw_live_daily`
- Classification: Private business data

## Grain

One row represents one LIVE performance day in the normalized daily layer.

If the source contains multiple LIVE sessions per day, session-level records
must be preserved before daily aggregation.

## Business Key

Preferred daily business identity:

`metric_date`

If session identifiers are available, the detailed identity should use:

`live_session_id + metric_date`

## Load Strategy

- Incremental ingestion by metric date
- Idempotent reruns
- UPSERT support for corrected historical metrics
- Late-arriving corrections supported
- File-level duplicate detection using file hash

## Core Metrics

The source may contain metrics including:

- LIVE-attributed GMV
- Direct LIVE GMV
- Indirect LIVE GMV
- LIVE SKU orders
- Direct LIVE SKU orders
- LIVE views
- LIVE stream count
- Customers
- Engagement metrics
- Conversion metrics
- LIVE advertising spend when available

## Data Quality Requirements

The ingestion pipeline must validate:

- Source file exists
- Source file is not empty
- Required reporting date exists
- Reporting date is parseable
- GMV fields are numeric
- Order metrics are numeric and non-negative
- View metrics are numeric and non-negative
- Stream counts are numeric and non-negative
- Duplicate daily or session records are detectable
- Unexpected schema drift stops ingestion

## Known Real-World Characteristics

The source contains characteristics that the pipeline must handle:

- Days with no LIVE activity
- Days with LIVE activity but no attributed GMV
- Multiple LIVE sessions on the same day
- Direct and indirect revenue attribution
- Sparse activity across the reporting window
- Historical corrections
- Different reporting windows from other business sources

## Derived Metrics

The downstream transformation layer may calculate:

- gmv_per_live_stream
- orders_per_live_stream
- views_per_live_stream
- live_conversion_rate
- direct_gmv_share
- indirect_gmv_share
- revenue_per_live_order

Derived metrics must safely handle zero denominators.

## Reconciliation Role

LIVE data may be reconciled against:

- Shop Analytics
- Order transactions
- Campaign performance
- Product performance

LIVE-attributed GMV must not automatically be expected to equal total shop GMV.

The reconciliation layer should preserve attribution differences and reporting
window differences.

## Privacy Classification

This source is primarily aggregate LIVE performance data.

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

`raw_live_daily`
-> `stg_live_daily`
-> `int_live_performance`
-> `fct_live_daily`

The LIVE fact model will support performance, conversion, and revenue
attribution analysis.

## Failure Policy

Critical failures include:

- unreadable source file
- missing reporting date
- invalid required numeric values
- incompatible schema drift
- duplicate records that violate the defined grain

Non-critical anomalies should be logged for downstream quality evaluation.

## Public Portfolio Policy

The original private LIVE export must not be committed to Git.

Public demonstrations and CI must use a portfolio-safe dataset preserving the
same time-series behavior, sparse activity patterns, and attribution scenarios
without exposing private business information.