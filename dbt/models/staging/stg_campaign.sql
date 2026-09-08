with source as (
    select * from {{ source('raw', 'campaign_daily') }}
)

select
    raw_campaign_daily_row_id as campaign_daily_row_id,
    {{ safe_date('metric_date') }} as metric_date,
    {{ safe_numeric('ad_cost') }} as ad_cost,
    {{ safe_bigint('sku_orders') }} as sku_orders,
    {{ safe_numeric('cost_per_order') }} as cost_per_order,
    {{ safe_numeric('gross_revenue') }} as gross_revenue,
    {{ safe_numeric('roi') }} as roi,
    upper({{ normalize_text('currency') }}) as currency,
    _source_file as source_file,
    _source_row_number as source_row_number,
    _batch_id as batch_id,
    _file_hash as file_hash,
    _ingested_at as ingested_at,
    _pipeline_run_id as pipeline_run_id,
    _ingestion_file_id as ingestion_file_id
from source
