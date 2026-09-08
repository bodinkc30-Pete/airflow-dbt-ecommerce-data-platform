with creators as (
    select
        {{ normalize_influencer_identity('creator_handle') }} as normalized_creator_handle,
        min(creator_handle) as canonical_creator_handle,
        count(*) as order_item_count
    from {{ ref('int_order_items_current') }}
    where creator_handle is not null
    group by 1
),

entities as (
    select * from {{ ref('influencer_entities') }}
)

select
    creators.normalized_creator_handle,
    creators.canonical_creator_handle,
    creators.order_item_count,
    entities.influencer_entity_key,
    entities.identity_method,
    entities.identity_confidence,
    entities.requires_manual_review as influencer_requires_manual_review,
    case
        when entities.influencer_entity_key is null
            then 'unmatched_influencer_entity'
        else 'matched_influencer_entity'
    end as creator_identity_match_status
from creators
left join entities
    on creators.normalized_creator_handle = entities.normalized_influencer_name
