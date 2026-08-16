# Source Contract 06 - TikTok Product Master

## Source Identity

- Source ID: `SRC_PRODUCT_MASTER`
- Domain: Product Master
- Source system: TikTok Seller / Product Analytics
- Source format: Excel export
- Target raw table: `raw_products`
- Classification: Private business data

## Grain

One row represents one product-level record.

The product master should preserve the latest known product attributes and
product-level performance metrics from the source export.

## Business Key

Preferred business identity:

`product_id`

Product ID must be treated as the stable business identifier when available.

Product name alone must not be treated as a reliable unique key.

## Load Strategy

- Snapshot-style ingestion
- Idempotent reruns
- UPSERT by product ID
- Historical corrections supported
- File-level duplicate detection using file hash
- Product lifecycle state changes must be preserved

## Core Attributes

The source may contain attributes including:

- Product ID
- Product name
- Product status
- Category
- Product image or reference URL
- Product-level sales metrics
- Product-level GMV
- Orders
- SKU orders
- Items sold
- Traffic metrics
- Conversion metrics
- Affiliate or content-attributed performance

## Data Quality Requirements

The ingestion pipeline must validate:

- Source file exists
- Source file is not empty
- Product ID exists
- Product ID is not null
- Product ID is standardized
- Product name is populated when required
- Product status is valid
- Numeric metrics are parseable
- Monetary values are valid
- Duplicate Product IDs are detectable
- Unexpected schema drift stops ingestion

## Known Real-World Characteristics

The source contains characteristics that the pipeline must handle:

- Products with multiple SKUs
- Active and inactive products
- Products with zero sales
- Large numbers of analytical columns
- Historical metric corrections
- Product lifecycle changes
- Differences between product-level and SKU-level reports
- Products that may exist in the product master but not in active SKU reports

## Product Lifecycle Policy

Product status must be preserved rather than deleting inactive products.

Examples of lifecycle states may include:

- active
- inactive
- unavailable
- archived
- unknown

Source-specific status values should be standardized in the staging layer.

## Reconciliation Role

Product Master may be reconciled against:

- SKU Master
- Order transactions
- Shop Analytics
- Product Card Traffic

The pipeline should support checks for:

- products without SKUs
- SKUs without valid products
- product GMV versus aggregated SKU GMV
- product order counts versus SKU order counts
- inactive products with unexpected sales activity

Differences must be evaluated using documented business rules.

## Privacy Classification

This source is primarily product-level business data.

Customer-level PII should not be present.

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

`raw_products`
-> `stg_products`
-> `int_product_performance`
-> `dim_product`

Product-level performance may also contribute to analytical fact models.

## Failure Policy

Critical failures include:

- unreadable source file
- missing Product ID
- invalid required identifiers
- incompatible schema drift
- duplicate Product IDs that violate the defined grain

Non-critical anomalies should be logged for downstream quality evaluation.

## Public Portfolio Policy

The original private Product Master export must not be committed to Git.

Public demonstrations and CI must use portfolio-safe product data preserving
the same product lifecycle, multi-SKU relationships, and reconciliation
scenarios without exposing private business information.