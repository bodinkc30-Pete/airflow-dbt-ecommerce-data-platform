with source as (
    select * from {{ source('raw', 'product_card_daily') }}
)

select
    raw_product_card_daily_row_id as product_card_daily_row_id,
    {{ safe_date('metric_date') }} as metric_date,
    {{ safe_bigint('product_card_views') }} as product_card_views,
    {{ safe_bigint('product_card_clicks') }} as product_card_clicks,
    {{ safe_bigint('customers') }} as customers,
    {{ safe_bigint('attributed_sku_orders') }} as attributed_sku_orders,
    {{ safe_numeric('product_card_gmv') }} as product_card_gmv,
    {{ safe_percent('add_to_cart_to_payment_rate') }} as add_to_cart_to_payment_rate,
    {{ safe_bigint('viewers') }} as viewers,
    {{ safe_bigint('add_to_cart_clicks') }} as add_to_cart_clicks,
    {{ safe_bigint('unique_product_clicks') }} as unique_product_clicks,
    {{ safe_bigint('add_to_cart_customers') }} as add_to_cart_customers,
    {{ safe_percent('product_click_to_add_to_cart_rate') }} as product_click_to_add_to_cart_rate,
    {{ safe_percent('view_to_product_click_rate') }} as view_to_product_click_rate,
    {{ safe_percent('view_to_payment_rate') }} as view_to_payment_rate,
    {{ safe_percent('product_click_to_payment_rate') }} as product_click_to_payment_rate,
    {{ safe_numeric('content_attributed_gmv') }} as content_attributed_gmv,
    _source_file as source_file,
    _source_row_number as source_row_number,
    _batch_id as batch_id,
    _file_hash as file_hash,
    _ingested_at as ingested_at,
    _pipeline_run_id as pipeline_run_id,
    _ingestion_file_id as ingestion_file_id
from source
