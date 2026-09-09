{{ config(
    materialized='incremental',
    unique_key='date_key',
    incremental_strategy='delete+insert',
    on_schema_change='fail'
) }}

with source as (
    select *
    from {{ ref('int_product_card_daily_current') }}
    where {{ incremental_window_predicate(
        'ingested_at',
        'ingested_at',
        'metric_date'
    ) }}
)

select
    to_char(metric_date, 'YYYYMMDD')::integer as date_key,
    product_card_views,
    product_card_clicks,
    customers,
    attributed_sku_orders,
    product_card_gmv,
    add_to_cart_to_payment_rate,
    viewers,
    add_to_cart_clicks,
    unique_product_clicks,
    add_to_cart_customers,
    product_click_to_add_to_cart_rate,
    view_to_product_click_rate,
    view_to_payment_rate,
    product_click_to_payment_rate,
    content_attributed_gmv,
    source_observation_count,
    source_file_count,
    pipeline_run_id,
    ingestion_file_id,
    ingested_at
from source
