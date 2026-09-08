with current_rows as (
    select count(*) as row_count from {{ ref('int_order_items_current') }}
),
enriched_rows as (
    select count(*) as row_count from {{ ref('int_order_items_enriched') }}
)
select 1
from current_rows cross join enriched_rows
where current_rows.row_count <> enriched_rows.row_count
