# Source Contract 01 - TikTok Seller Orders

## Source Identity

- Source ID: `SRC_ORDERS`
- Domain: Sales / Orders
- Source system: TikTok Seller
- Source format: CSV export
- Target raw table: `raw_orders`
- Classification: Private business data

## Grain

One row represents one order-SKU line.

An Order ID can therefore appear on multiple rows when an order contains
multiple SKUs.

## Business Keys

Primary business identity:

`Order ID + SKU ID + source line identity`

Order ID alone must not be assumed to be unique at raw-row grain.

## Load Strategy

- Incremental ingestion
- Idempotent reruns
- UPSERT support for order lifecycle updates
- Late-arriving status updates supported
- File-level duplicate detection using file hash

## Data Quality Requirements

The ingestion pipeline must validate:

- Source file exists
- Source file is not empty
- Required columns exist
- Order ID is populated
- SKU ID is populated
- SKU IDs are trimmed and standardized
- Required datetime fields are parseable
- Required numeric fields are valid
- Order statuses conform to the supported domain
- Duplicate raw records are detectable
- Unexpected schema drift stops ingestion

## Known Real-World Characteristics

The source contains real-world characteristics that the pipeline must handle:

- Multi-line orders
- Order lifecycle/status changes
- Identifier whitespace inconsistencies
- Multiple datetime fields
- Numeric and monetary fields
- Personally identifiable information
- Potential late-arriving updates

## Privacy Classification

The raw export contains personally identifiable information, including fields
related to buyers, recipients, phone numbers, addresses, and tax/invoice data.

Raw PII must remain in the private ingestion layer.

PII must not be published to:

- dbt marts
- demo datasets
- GitHub
- CI artifacts
- portfolio outputs

## Raw Lineage Metadata

The pipeline adds the following metadata:

- `_source_file`
- `_source_row_number`
- `_batch_id`
- `_file_hash`
- `_ingested_at`
- `_pipeline_run_id`

These fields provide traceability from a database record back to its ingestion
batch and source file.

## Downstream Models

Planned downstream flow:

`raw_orders`
-> `stg_orders`
-> `int_order_items`
-> `fct_orders`
-> `fct_daily_sales`

## Failure Policy

The ingestion task must fail before database loading when a critical contract
violation occurs.

Critical examples:

- missing required column
- missing Order ID
- invalid required datetime
- unreadable source file
- incompatible schema drift

Non-critical anomalies may be recorded for downstream data-quality handling.

## Public Portfolio Policy

The original private source file will never be committed to Git.

Public demonstrations and CI will use a portfolio-safe dataset preserving the
same schema and engineering edge cases without exposing private business or
personal data.