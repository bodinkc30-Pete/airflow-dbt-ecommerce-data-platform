select
    'influencer_observation_v1_' || md5(influencer_row_id::text)
        as influencer_observation_key,
    coalesce(influencer_entity_key, 'influencer_unknown') as influencer_key,
    coalesce(to_char(ingested_at::date, 'YYYYMMDD')::integer, 0)
        as observation_date_key,
    influencer_row_id,
    influencer_name as observed_influencer_name,
    follower_count,
    engagement_rate,
    budget,
    identity_method,
    identity_confidence,
    source_row_number,
    pipeline_run_id,
    ingestion_file_id,
    ingested_at
from {{ ref('influencer_identity_map') }}
