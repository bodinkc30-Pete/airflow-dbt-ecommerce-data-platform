with staged as (
    select * from {{ ref('stg_influencer') }}
),

normalized as (
    select
        influencer_row_id,
        influencer_name,
        {{ normalize_influencer_identity('influencer_name') }}
            as normalized_influencer_name,
        follower_count,
        engagement_rate,
        budget,
        ingested_at,
        pipeline_run_id,
        ingestion_file_id,
        source_file,
        source_row_number
    from staged
)

select
    influencer_row_id,
    influencer_name,
    normalized_influencer_name,
    case
        when normalized_influencer_name is not null
        then 'infl_name_v1_' || md5(
            'normalized_name_v1|' || normalized_influencer_name
        )
    end as influencer_entity_key,
    'normalized_name_v1' as identity_method,
    'provisional' as identity_confidence,
    follower_count,
    engagement_rate,
    budget,
    ingested_at,
    pipeline_run_id,
    ingestion_file_id,
    source_file,
    source_row_number
from normalized
