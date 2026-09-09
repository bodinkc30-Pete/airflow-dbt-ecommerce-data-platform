with source_latest as (
    select distinct on (order_id)
        order_id,
        order_amount,
        shipping_fee_after_discount,
        original_shipping_fee,
        payment_platform_discount,
        taxes
    from {{ ref('int_order_items_current') }}
    order by order_id, ingested_at desc, pipeline_run_id desc, ingestion_file_id desc, order_row_id desc
),
source_totals as (
    select
        coalesce(sum(order_amount), 0) as order_amount,
        coalesce(sum(shipping_fee_after_discount), 0) as shipping_fee,
        coalesce(sum(original_shipping_fee), 0) as original_shipping_fee,
        coalesce(sum(payment_platform_discount), 0) as payment_discount,
        coalesce(sum(taxes), 0) as taxes
    from source_latest
),
warehouse_totals as (
    select
        coalesce(sum(order_amount), 0) as order_amount,
        coalesce(sum(shipping_fee_after_discount), 0) as shipping_fee,
        coalesce(sum(original_shipping_fee), 0) as original_shipping_fee,
        coalesce(sum(payment_platform_discount), 0) as payment_discount,
        coalesce(sum(taxes), 0) as taxes
    from {{ ref('fact_orders') }}
)
select *
from source_totals cross join warehouse_totals
where source_totals.order_amount <> warehouse_totals.order_amount
   or source_totals.shipping_fee <> warehouse_totals.shipping_fee
   or source_totals.original_shipping_fee <> warehouse_totals.original_shipping_fee
   or source_totals.payment_discount <> warehouse_totals.payment_discount
   or source_totals.taxes <> warehouse_totals.taxes
