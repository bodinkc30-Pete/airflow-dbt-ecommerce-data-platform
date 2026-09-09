{{ config(
    materialized='incremental',
    unique_key='date_key',
    incremental_strategy='delete+insert',
    on_schema_change='fail'
) }}

with source as (
    select *
    from {{ ref('int_live_daily_current') }}
    where {{ incremental_window_predicate(
        'ingested_at',
        'ingested_at',
        'metric_date'
    ) }}
)

select
    to_char(metric_date, 'YYYYMMDD')::integer as date_key,
    live_attributed_gmv,
    live_direct_gmv,
    live_indirect_gmv,
    display_gpm,
    live_stream_count,
    gmv_generating_live_stream_count,
    live_attributed_items_sold,
    live_direct_items_sold,
    live_indirect_items_sold,
    attributed_sku_orders,
    live_direct_sku_orders,
    live_indirect_sku_orders,
    customers_search,
    live_click_through_rate,
    live_sku_order_conversion_rate,
    live_views,
    average_live_watch_duration,
    source_observation_count,
    source_file_count,
    pipeline_run_id,
    ingestion_file_id,
    ingested_at
from source
