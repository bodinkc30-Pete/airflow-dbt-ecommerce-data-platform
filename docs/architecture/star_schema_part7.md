# PART 7 - Data Warehouse Star Schema

## Purpose

PART 7 creates the analytics consumption layer from validated intermediate and identity models.
The warehouse is materialized as PostgreSQL tables in `analytics_marts`.

## Conformed Dimensions

- `dim_date`: role-playing calendar dimension; `date_key = 0` is Unknown.
- `dim_product`: one current Product plus `product_unknown`.
- `dim_sku`: one current SKU plus `sku_unknown`; links to Product.
- `dim_influencer`: one provisional entity plus `influencer_unknown`.

## Fact Grains

- `fact_orders`: one row per Order ID.
- `fact_order_items`: one row per current Order ID + SKU ID.
- `fact_shop_daily`: one row per shop metric date.
- `fact_campaign_daily`: one row per campaign metric date.
- `fact_live_daily`: one row per LIVE metric date.
- `fact_product_card_daily`: one row per Product Card metric date.
- `fact_influencer_observation`: one row per influencer roster source observation.

## Order Grain Boundary

Private read-only profiling proved that multi-SKU orders exist.
Order-level monetary values must therefore not be summed at SKU-line grain.

`fact_orders` owns order-level measures such as order amount, shipping fees, payment-platform discount, and taxes.
`fact_order_items` owns SKU-line measures such as quantity, SKU subtotals, SKU discounts, and line-observed refund amount.
`order_channel` remains at item grain because real multi-line orders can contain different observed values.

## Unknown Members

Warehouse facts never drop unresolved references.
Unmatched SKU, Product, Influencer, or optional date references route to explicit Unknown members.
Match-status columns remain available for troubleshooting and coverage reporting.

## Measure Semantics

Additive counts and monetary values may only be aggregated at their documented fact grain.
ROI, conversion rates, click-through rates, and similar ratios are non-additive and must not be summed across dates.
Influencer follower, engagement, and budget values are observation facts, not dimension attributes to overwrite.

## Materialization

Marts are tables to prevent dashboards and analysts from repeatedly expanding the full staging/intermediate view graph.
Incremental dbt materializations are intentionally deferred to PART 9.

## Privacy Boundary

The warehouse is built from analytics-safe staging and does not reintroduce buyer phone, address, tax identity, or free-text buyer fields.
Creator/influencer operational identifiers remain private business data; public demos must use synthetic or masked values.
