select influencer_entity_key
from {{ ref('influencer_identity_map') }}
where influencer_entity_key !~ '^infl_name_v1_[0-9a-f]{32}$'
