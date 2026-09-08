with source as (
    select * from {{ source('raw', 'influencer_roster') }}
)

select
    raw_influencer_row_id as influencer_row_id,
    {{ normalize_text('influencer_name') }} as influencer_name,
    {{ safe_bigint('follower_count') }} as follower_count,
    {{ safe_percent('engagement_rate') }} as engagement_rate,
    {{ safe_numeric('budget') }} as budget,
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
