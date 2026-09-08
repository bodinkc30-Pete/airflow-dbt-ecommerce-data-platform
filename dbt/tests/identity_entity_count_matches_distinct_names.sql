with expected as (
    select count(distinct normalized_influencer_name) as entity_count
    from {{ ref('influencer_identity_map') }}
),
actual as (
    select count(*) as entity_count
    from {{ ref('influencer_entities') }}
)

select expected.entity_count as expected_count,
       actual.entity_count as actual_count
from expected
cross join actual
where expected.entity_count <> actual.entity_count
