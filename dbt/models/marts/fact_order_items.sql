{{ config(
    materialized='incremental',
    unique_key='order_item_key',
    incremental_strategy='delete+insert',
    on_schema_change='fail'
) }}

with orders as (
    select *
    from {{ ref('int_order_items_enriched') }}
    where {{ incremental_window_predicate(
        'ingested_at',
        'ingested_at',
        'created_at::date'
    ) }}
)

select
    order_item_key,
    order_id,
    case when sku_match_status = 'matched_sku'
        then 'sku_v1_' || md5(sku_id)
        else 'sku_unknown' end as sku_key,
    case when product_match_status = 'matched_product'
        then 'product_v1_' || md5(catalog_product_id)
        else 'product_unknown' end as product_key,
    coalesce(influencer_entity_key, 'influencer_unknown') as influencer_key,
    coalesce(to_char(created_at::date, 'YYYYMMDD')::integer, 0) as created_date_key,
    coalesce(to_char(paid_at::date, 'YYYYMMDD')::integer, 0) as paid_date_key,
    coalesce(to_char(ready_to_ship_at::date, 'YYYYMMDD')::integer, 0) as ready_to_ship_date_key,
    coalesce(to_char(shipped_at::date, 'YYYYMMDD')::integer, 0) as shipped_date_key,
    coalesce(to_char(delivered_at::date, 'YYYYMMDD')::integer, 0) as delivered_date_key,
    coalesce(to_char(cancelled_at::date, 'YYYYMMDD')::integer, 0) as cancelled_date_key,
    sku_id as source_sku_id,
    seller_sku,
    creator_handle,
    variation,
    order_status,
    order_substatus,
    cancellation_return_type,
    order_type,
    quantity,
    returned_quantity,
    sku_unit_original_price,
    sku_subtotal_before_discount,
    sku_platform_discount,
    sku_seller_discount,
    sku_subtotal_after_discount,
    order_refund_amount,
    weight_kg,
    fulfillment_type,
    warehouse_name,
    delivery_option,
    shipping_provider_name,
    payment_method,
    product_category,
    checked_status,
    order_channel,
    request_tax_invoice,
    sku_match_status,
    product_match_status,
    creator_identity_match_status,
    creator_identity_method,
    creator_identity_confidence,
    influencer_requires_manual_review,
    source_observation_count,
    source_file_count,
    pipeline_run_id,
    ingestion_file_id,
    ingested_at
from orders
