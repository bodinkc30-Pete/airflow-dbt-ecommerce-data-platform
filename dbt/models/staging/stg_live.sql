with source as (
    select * from {{ source('raw', 'live_daily') }}
)

select
    raw_live_daily_row_id as live_daily_row_id,
    {{ safe_date('metric_date') }} as metric_date,
    {{ safe_numeric('live_attributed_gmv') }} as live_attributed_gmv,
    {{ safe_numeric('live_direct_gmv') }} as live_direct_gmv,
    {{ safe_numeric('live_indirect_gmv') }} as live_indirect_gmv,
    {{ safe_numeric('display_gpm') }} as display_gpm,
    {{ safe_bigint('live_stream_count') }} as live_stream_count,
    {{ safe_bigint('gmv_generating_live_stream_count') }} as gmv_generating_live_stream_count,
    {{ safe_bigint('live_attributed_items_sold') }} as live_attributed_items_sold,
    {{ safe_bigint('live_direct_items_sold') }} as live_direct_items_sold,
    {{ safe_bigint('live_indirect_items_sold') }} as live_indirect_items_sold,
    {{ safe_bigint('attributed_sku_orders') }} as attributed_sku_orders,
    {{ safe_bigint('live_direct_sku_orders') }} as live_direct_sku_orders,
    {{ safe_bigint('live_indirect_sku_orders') }} as live_indirect_sku_orders,
    {{ safe_bigint('customers_search') }} as customers_search,
    {{ safe_percent('live_click_through_rate') }} as live_click_through_rate,
    {{ safe_percent('live_sku_order_ctor') }} as live_sku_order_conversion_rate,
    {{ safe_bigint('live_views') }} as live_views,
    {{ normalize_text('average_live_watch_duration') }} as average_live_watch_duration,
    _source_file as source_file,
    _source_row_number as source_row_number,
    _batch_id as batch_id,
    _file_hash as file_hash,
    _ingested_at as ingested_at,
    _pipeline_run_id as pipeline_run_id,
    _ingestion_file_id as ingestion_file_id
from source
