{{ config(severity='error', tags=['dq_blocking']) }}

with items as (
    select
        order_id,
        count(*) as sku_line_count,
        count(distinct source_sku_id) as distinct_sku_count,
        sum(quantity) as total_item_quantity,
        sum(returned_quantity) as total_returned_quantity
    from {{ ref('fact_order_items') }}
    group by order_id
),
orders as (
    select * from {{ ref('fact_orders') }}
)
select coalesce(orders.order_id, items.order_id) as order_id
from orders
full outer join items using (order_id)
where orders.order_id is null
   or items.order_id is null
   or orders.sku_line_count is distinct from items.sku_line_count
   or orders.distinct_sku_count is distinct from items.distinct_sku_count
   or orders.total_item_quantity is distinct from items.total_item_quantity
   or orders.total_returned_quantity is distinct from items.total_returned_quantity
