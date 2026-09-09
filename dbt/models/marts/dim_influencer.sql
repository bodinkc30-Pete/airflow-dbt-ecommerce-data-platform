with entities as (
    select * from {{ ref('influencer_entities') }}
)

select
    'influencer_unknown'::text as influencer_key,
    null::text as influencer_entity_key,
    null::text as normalized_influencer_name,
    'Unknown Influencer'::text as canonical_influencer_name,
    'unknown'::text as identity_method,
    'unknown'::text as identity_confidence,
    0::bigint as source_row_count,
    0::bigint as source_file_count,
    0::bigint as duplicate_snapshot_count,
    0::bigint as conflicting_snapshot_count,
    false::boolean as requires_manual_review,
    null::timestamptz as first_seen_at,
    null::timestamptz as last_seen_at
union all
select
    influencer_entity_key as influencer_key,
    influencer_entity_key,
    normalized_influencer_name,
    canonical_influencer_name,
    identity_method,
    identity_confidence,
    source_row_count,
    source_file_count,
    duplicate_snapshot_count,
    conflicting_snapshot_count,
    requires_manual_review,
    first_seen_at,
    last_seen_at
from entities
