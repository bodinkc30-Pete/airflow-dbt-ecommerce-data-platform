# Source Contract 07 - TikTok SKU Master

## Source Identity

- Source ID: `SRC_SKU_MASTER`
- Domain: SKU Master
- Source system: TikTok Seller / Product Analytics
- Source format: Excel export
- Target raw table: `raw_skus`
- Classification: Private business data

## Grain

One row represents one SKU-level record.

Each SKU should belong to one product in the normalized model.

## Business Key

Preferred business identity:

`sku_id`

SKU ID must be treated as the stable SKU-level identifier when available.

SKU name or seller SKU alone must not automatically be assumed to be unique.

## Relationship Key

Each SKU should reference:

`product_id`

This relationship will be validated downstream against the Product Master.

## Load Strategy

- Snapshot-style ingestion
- Idempotent reruns
- UPSERT by SKU ID
- Historical corrections supported
- File-level duplicate detection using file hash
- SKU lifecycle state changes must be preserved

## Core Attributes

The source may contain attributes including:

- SKU ID
- Seller SKU
- Product ID
- Product name
- SKU name
- Variant attributes
- Product status
- SKU status
- SKU-level GMV
- SKU orders
- Items sold
- Traffic metrics
- Conversion metrics

## Data Quality Requirements

The ingestion pipeline must validate:

- Source file exists
- Source file is not empty
- SKU ID exists
- SKU ID is not null
- SKU ID is standardized
- Leading and trailing whitespace is removed from identifiers
- Product ID exists when required
- Product ID is standardized
- Numeric metrics are parseable
- Monetary values are valid
- Duplicate SKU IDs are detectable
- Unexpected schema drift stops ingestion

## Known Real-World Characteristics

The source contains characteristics that the pipeline must handle:

- Multiple SKUs belonging to one product
- SKU identifiers containing inconsistent whitespace
- Active and inactive SKUs
- SKUs with zero sales
- Product and SKU reports with slightly different totals
- Historical metric corrections
- SKU lifecycle changes
- SKUs that may disappear from later active-product exports

## Identifier Standardization Policy

Identifier fields must be normalized before relationship validation.

At minimum:

- trim leading whitespace
- trim trailing whitespace
- preserve identifiers as strings
- do not cast large IDs to floating-point values
- do not remove meaningful leading zeros
- reject or quarantine invalid empty identifiers

This policy is especially important for TikTok identifiers that may exceed
normal integer ranges in downstream tools.

## SKU Lifecycle Policy

SKU status must be preserved rather than deleting inactive SKU records.

Normalized lifecycle states may include:

- active
- inactive
- unavailable
- archived
- unknown

Source-specific status values should be standardized in the staging layer.

## Reconciliation Role

SKU Master may be reconciled against:

- Product Master
- Order transactions
- Shop Analytics
- Product Card Traffic

The pipeline should support checks for:

- SKUs without valid products
- products without active SKUs
- SKU GMV versus product GMV
- SKU order counts versus product order counts
- SKU items sold versus product items sold
- order-line SKU IDs not present in SKU Master

Small differences between source reports may be handled using documented
reconciliation tolerances.

## Privacy Classification

This source is primarily SKU-level business data.

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

`raw_skus`
-> `stg_skus`
-> `dim_sku`

SKU-level performance may also contribute to:

`int_product_performance`

and downstream analytical fact models.

## Failure Policy

Critical failures include:

- unreadable source file
- missing SKU ID
- invalid required identifiers
- incompatible schema drift
- duplicate SKU IDs that violate the defined grain

Relationship violations such as an unknown Product ID should be captured for
data-quality investigation and may fail the quality gate depending on severity.

## Public Portfolio Policy

The original private SKU Master export must not be committed to Git.

Public demonstrations and CI must use portfolio-safe SKU data preserving the
same product-SKU relationships, identifier-cleaning requirements, lifecycle
states, and reconciliation scenarios without exposing private business
information.