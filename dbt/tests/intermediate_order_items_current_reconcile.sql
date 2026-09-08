with expected as (
    select count(*) as row_count
    from (
        select distinct order_id, sku_id
        from {{ ref('stg_orders') }}
        where order_id is not null and sku_id is not null
    ) business_keys
),
actual as (
    select count(*) as row_count from {{ ref('int_order_items_current') }}
)
select 1
from expected cross join actual
where expected.row_count <> actual.row_count
