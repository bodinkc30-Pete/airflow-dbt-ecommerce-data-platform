with source as (
    select * from {{ source('raw', 'products') }}
)

select
    raw_product_row_id as product_row_id,
    {{ normalize_text('product_id') }} as product_id,
    {{ normalize_text('product_name') }} as product_name,
    {{ normalize_text('gmv_tier') }} as gmv_tier,
    {{ normalize_text('product_status') }} as product_status,
    source_payload,
    {{ normalize_text('header_schema_version') }} as header_schema_version,
    _source_file as source_file,
    _source_row_number as source_row_number,
    _batch_id as batch_id,
    _file_hash as file_hash,
    _ingested_at as ingested_at,
    _pipeline_run_id as pipeline_run_id,
    _ingestion_file_id as ingestion_file_id
from source
