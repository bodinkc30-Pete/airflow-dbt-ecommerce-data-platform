with intermediate as (
    select
        coalesce(sum(quantity), 0) as quantity,
        coalesce(sum(order_refund_amount), 0) as refund_amount,
        coalesce(sum(sku_subtotal_after_discount), 0) as item_revenue
    from {{ ref('int_order_items_enriched') }}
),
warehouse as (
    select
        coalesce(sum(quantity), 0) as quantity,
        coalesce(sum(order_refund_amount), 0) as refund_amount,
        coalesce(sum(sku_subtotal_after_discount), 0) as item_revenue
    from {{ ref('fact_order_items') }}
)
select *
from intermediate cross join warehouse
where intermediate.quantity <> warehouse.quantity
   or intermediate.refund_amount <> warehouse.refund_amount
   or intermediate.item_revenue <> warehouse.item_revenue
