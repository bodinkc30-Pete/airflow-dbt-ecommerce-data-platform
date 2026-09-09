with items as (
    select * from {{ ref('int_order_items_current') }}
),

order_stats as (
    select
        order_id,
        count(*) as sku_line_count,
        count(distinct sku_id) as distinct_sku_count,
        sum(quantity) as total_item_quantity,
        sum(returned_quantity) as total_returned_quantity,
        sum(source_observation_count) as source_observation_count,
        count(distinct ingestion_file_id) as source_file_count,
        min(ingested_at) as first_seen_at,
        max(ingested_at) as last_seen_at
    from items
    group by order_id
),

latest_order_state as (
    select distinct on (order_id) *
    from items
    order by
        order_id,
        ingested_at desc,
        pipeline_run_id desc,
        ingestion_file_id desc,
        order_row_id desc
)
select
    'order_v1_' || md5(latest.order_id) as order_key,
    latest.order_id,
    coalesce(to_char(latest.created_at::date, 'YYYYMMDD')::integer, 0) as created_date_key,
    coalesce(to_char(latest.paid_at::date, 'YYYYMMDD')::integer, 0) as paid_date_key,
    coalesce(to_char(latest.ready_to_ship_at::date, 'YYYYMMDD')::integer, 0) as ready_to_ship_date_key,
    coalesce(to_char(latest.shipped_at::date, 'YYYYMMDD')::integer, 0) as shipped_date_key,
    coalesce(to_char(latest.delivered_at::date, 'YYYYMMDD')::integer, 0) as delivered_date_key,
    coalesce(to_char(latest.cancelled_at::date, 'YYYYMMDD')::integer, 0) as cancelled_date_key,
    latest.order_status,
    latest.order_substatus,
    latest.cancellation_return_type,
    latest.order_type,
    latest.order_amount,
    latest.shipping_fee_after_discount,
    latest.original_shipping_fee,
    latest.shipping_fee_seller_discount,
    latest.shipping_fee_platform_discount,
    latest.payment_platform_discount,
    latest.taxes,
    latest.fulfillment_type,
    latest.warehouse_name,
    latest.delivery_option,
    latest.shipping_provider_name,
    latest.payment_method,
    latest.request_tax_invoice,
    stats.sku_line_count,
    stats.distinct_sku_count,
    stats.total_item_quantity,
    stats.total_returned_quantity,
    stats.source_observation_count,
    stats.source_file_count,
    latest.pipeline_run_id,
    latest.ingestion_file_id,
    stats.first_seen_at,
    stats.last_seen_at
from latest_order_state latest
join order_stats stats using (order_id)
