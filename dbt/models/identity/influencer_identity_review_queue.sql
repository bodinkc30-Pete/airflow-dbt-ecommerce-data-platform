select
    influencer_entity_key,
    normalized_influencer_name,
    canonical_influencer_name,
    identity_method,
    identity_confidence,
    source_row_count,
    source_file_count,
    name_variant_count,
    duplicate_snapshot_count,
    conflicting_snapshot_count,
    first_seen_at,
    last_seen_at
from {{ ref('influencer_entities') }}
where requires_manual_review
