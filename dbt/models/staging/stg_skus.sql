with source as (
    select * from {{ source('raw', 'skus') }}
)

select
    raw_sku_row_id as sku_row_id,
    {{ normalize_text('sku_id') }} as sku_id,
    {{ normalize_text('product_id') }} as product_id,
    {{ normalize_text('sku_name') }} as sku_name,
    {{ normalize_text('sku_status') }} as sku_status,
    {{ safe_numeric('gmv') }} as gmv,
    {{ safe_bigint('sku_orders') }} as sku_orders,
    {{ safe_bigint('items_sold') }} as items_sold,
    _source_file as source_file,
    _source_row_number as source_row_number,
    _batch_id as batch_id,
    _file_hash as file_hash,
    _ingested_at as ingested_at,
    _pipeline_run_id as pipeline_run_id,
    _ingestion_file_id as ingestion_file_id
from source
