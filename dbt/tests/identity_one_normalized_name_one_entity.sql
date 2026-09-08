select
    normalized_influencer_name,
    count(distinct influencer_entity_key) as entity_key_count
from {{ ref('influencer_identity_map') }}
group by normalized_influencer_name
having count(distinct influencer_entity_key) <> 1
