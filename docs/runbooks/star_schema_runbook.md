# Star Schema Runbook

## Build

From the repository root, run:

```powershell
dbt compile --project-dir dbt --profiles-dir dbt
dbt build --project-dir dbt --profiles-dir dbt
```

For warehouse-only iteration when upstream objects are already valid:

```powershell
dbt run --project-dir dbt --profiles-dir dbt --select path:models/marts
dbt test --project-dir dbt --profiles-dir dbt --select path:models/marts
```

## Expected Warehouse Schema

All PART 7 models are physical tables in `analytics_marts`.
There must be four dimensions and seven facts.

## Failure Triage

If a relationship test fails, inspect the fact match-status first; unresolved references must route to the appropriate Unknown member rather than disappear.
If order totals look inflated, verify that order-level measures are aggregated from `fact_orders`, not `fact_order_items`.
If a daily rate looks inflated, verify that ROI/conversion/CTR values are not being summed across dates.

## Grain Checks

- `fact_orders`: one row per Order ID.
- `fact_order_items`: one row per Order-SKU business key.
- Daily facts: one row per valid metric date per business process.
- `fact_influencer_observation`: one row per source observation.

## Unknown Members

Expected reserved keys are:

- `date_key = 0`
- `product_unknown`
- `sku_unknown`
- `influencer_unknown`

Unknown usage is valid when source references are missing or unresolved; it is not permission to silently repair the source.

## Recovery

After correcting a warehouse model, rerun marts and their tests. For release validation, always rerun the full dbt build and project regression suite.
Do not alter raw transaction ownership or ingestion contracts to repair a warehouse-only failure.
