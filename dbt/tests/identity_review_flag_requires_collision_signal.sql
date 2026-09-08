select influencer_entity_key
from {{ ref('influencer_entities') }}
where requires_manual_review
  and name_variant_count <= 1
  and conflicting_snapshot_count = 0

union all

select influencer_entity_key
from {{ ref('influencer_entities') }}
where not requires_manual_review
  and (
      name_variant_count > 1
      or conflicting_snapshot_count > 0
  )
