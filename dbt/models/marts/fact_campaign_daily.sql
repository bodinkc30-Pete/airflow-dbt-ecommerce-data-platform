{{ config(
    materialized='incremental',
    unique_key='date_key',
    incremental_strategy='delete+insert',
    on_schema_change='fail'
) }}

with source as (
    select *
    from {{ ref('int_campaign_daily_current') }}
    where {{ incremental_window_predicate(
        'ingested_at',
        'ingested_at',
        'metric_date'
    ) }}
)

select
    to_char(metric_date, 'YYYYMMDD')::integer as date_key,
    ad_cost,
    sku_orders,
    cost_per_order,
    gross_revenue,
    roi,
    currency,
    source_observation_count,
    source_file_count,
    pipeline_run_id,
    ingestion_file_id,
    ingested_at
from source
