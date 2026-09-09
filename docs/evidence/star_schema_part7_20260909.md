# PART 7 Runtime Evidence - 2026-09-09

## Research Evidence

Foundation review confirmed one current business key per Product, SKU, Order-SKU, Influencer entity, and daily metric date in the intermediate layer.

Private read-only profiling, with no database write, found:

- 5,249 Order-SKU rows.
- 5,188 distinct Orders.
- 58 multi-line Orders containing 119 SKU rows.
- 61 extra line rows that would repeat order-level amounts at item grain.
- 12 distinct Products and 15 distinct SKUs.
- 92 influencer observations and 88 normalized influencer entities.

Selected order-level attributes were stable across SKU lines in the profiled export.
Refund amount and order-channel observations were not universally stable, so they were not promoted as single order-level attributes.

## Warehouse Runtime

`dbt run --select path:models/marts` created 11 PostgreSQL tables in `analytics_marts`.
Baseline runtime row counts reconcile to the current intermediate/identity state.

Each conformed dimension contains exactly one Unknown member.
Foreign-key validation reported zero orphans for Product, SKU, Influencer, and every role-playing date reference.

## Multi-Line Order Scenario

A synthetic two-SKU order was inserted for runtime validation only.
After rebuilding the two order facts:

- `fact_order_items` produced 2 rows.
- `fact_orders` produced 1 row.
- order amount appeared once at order grain.
- SKU line count was 2.
- total item quantity was 3.
- `fact_order_items` contained no `order_amount` column.

The synthetic raw rows and their audit run/file records were deleted, then marts were rebuilt.
Post-cleanup synthetic residue was zero in raw, audit, and warehouse tables.

## Warehouse Test Evidence

Focused marts tests passed 70 of 70 after the order-grain split and BOM correction.
The tests cover unique fact grains, conformed-dimension relationships, Unknown routing, date coverage, row-count reconciliation, and measure reconciliation.

## Performance Sanity

An aggregate query joining `fact_order_items`, `dim_sku`, and `dim_product` plans directly against materialized warehouse tables using simple scans and hash joins rather than expanding the full upstream view graph.

No private source values, client identifiers, or local private-data paths are stored in this evidence file.
