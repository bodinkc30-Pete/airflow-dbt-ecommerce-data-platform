with mapped as (
    select * from {{ ref('influencer_identity_map') }}
),

snapshot_groups as (
    select
        influencer_entity_key,
        ingestion_file_id,
        count(*) as rows_in_snapshot,
        count(distinct influencer_name) as name_variant_count,
        count(distinct follower_count)
            filter (where follower_count is not null) as follower_value_count,
        count(distinct engagement_rate)
            filter (where engagement_rate is not null) as engagement_rate_value_count,
        count(distinct budget)
            filter (where budget is not null) as budget_value_count
    from mapped
    group by
        influencer_entity_key,
        ingestion_file_id
),

snapshot_summary as (
    select
        influencer_entity_key,
        count(*) filter (where rows_in_snapshot > 1) as duplicate_snapshot_count,
        count(*) filter (
            where rows_in_snapshot > 1
              and (
                  name_variant_count > 1
                  or follower_value_count > 1
                  or engagement_rate_value_count > 1
                  or budget_value_count > 1
              )
        ) as conflicting_snapshot_count
    from snapshot_groups
    group by influencer_entity_key
),

entity_rollup as (
    select
        influencer_entity_key,
        normalized_influencer_name,
        min(influencer_name) as canonical_influencer_name,
        min(identity_method) as identity_method,
        min(identity_confidence) as identity_confidence,
        count(*) as source_row_count,
        count(distinct ingestion_file_id) as source_file_count,
        count(distinct influencer_name) as name_variant_count,
        min(ingested_at) as first_seen_at,
        max(ingested_at) as last_seen_at,
        min(pipeline_run_id) as first_pipeline_run_id,
        max(pipeline_run_id) as last_pipeline_run_id
    from mapped
    group by
        influencer_entity_key,
        normalized_influencer_name
)
select
    entity_rollup.*,
    snapshot_summary.duplicate_snapshot_count,
    snapshot_summary.conflicting_snapshot_count,
    (
        entity_rollup.name_variant_count > 1
        or snapshot_summary.conflicting_snapshot_count > 0
    ) as requires_manual_review
from entity_rollup
join snapshot_summary using (influencer_entity_key)
