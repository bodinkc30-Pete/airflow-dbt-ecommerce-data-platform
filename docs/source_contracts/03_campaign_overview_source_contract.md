# Source Contract 03 - TikTok Campaign Overview

## Source Identity

- Source ID: `SRC_CAMPAIGN_OVERVIEW`
- Domain: Marketing / Advertising
- Source system: TikTok Seller / Ads
- Source format: Excel export
- Target raw table: `raw_campaign_daily`
- Classification: Private business data

## Grain

One row represents one campaign-performance day.

The normalized daily layer should preserve one record per reporting date and
campaign identity when campaign-level identifiers are available.

## Business Key

Preferred business identity:

`campaign_id + metric_date`

If the export does not provide a stable campaign identifier, the pipeline must
derive a documented surrogate identity using available campaign attributes.

## Load Strategy

- Incremental ingestion by metric date
- Idempotent reruns
- UPSERT support for corrected historical campaign metrics
- Late-arriving corrections supported
- File-level duplicate detection using file hash

## Core Metrics

The source may contain metrics including:

- Ad spend / cost
- Orders
- Cost per order
- Gross revenue
- ROI / ROAS
- Currency
- Campaign identifiers or names
- Reporting date

## Data Quality Requirements

The ingestion pipeline must validate:

- Source file exists
- Source file is not empty
- Required reporting date exists
- Reporting date is parseable
- Spend is numeric
- Revenue is numeric
- Orders are numeric and non-negative
- Currency values are valid
- ROI values are numeric when present
- Duplicate campaign-day records are detectable
- Unexpected schema drift stops ingestion

## Known Real-World Characteristics

The source contains characteristics that the pipeline must handle:

- Sparse campaign activity
- Days with no advertising spend
- Historical corrections
- Variable daily spend
- Variable daily revenue
- ROI changes across dates
- Reporting windows that may not match other business sources exactly

## Derived Metrics

The downstream transformation layer may calculate:

- calculated_roi = revenue / spend
- cost_per_order = spend / orders
- revenue_per_order = revenue / orders
- daily_spend_share
- daily_revenue_share

Derived metrics must safely handle zero denominators.

## Reconciliation Role

Campaign data may be reconciled against:

- Shop Analytics
- Order transactions
- Product performance
- Product Card traffic

Campaign-attributed revenue must not automatically be expected to equal total
shop GMV because attribution logic and reporting windows may differ.

Reconciliation should record:

- comparison period
- campaign revenue
- shop revenue
- absolute difference
- percentage difference
- reconciliation status

## Privacy Classification

This source is primarily aggregate marketing data.

It should not require customer-level PII for downstream analytics.

Any unexpected personal information found in the source must remain private.

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

`raw_campaign_daily`
-> `stg_campaign_daily`
-> `int_marketing_performance`
-> `fct_campaign_daily`

The campaign fact model will support marketing efficiency and attribution
analysis.

## Failure Policy

Critical failures include:

- unreadable source file
- missing reporting date
- invalid required numeric values
- incompatible schema drift
- duplicate records that violate the defined grain

Non-critical anomalies should be logged for downstream quality evaluation.

## Public Portfolio Policy

The original private campaign export must not be committed to Git.

Public demonstrations and CI must use a portfolio-safe dataset preserving the
same time-series behavior, spend/revenue relationships, and engineering edge
cases without exposing private business information.