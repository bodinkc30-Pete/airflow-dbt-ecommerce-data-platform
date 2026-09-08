with entity_total as (
    select coalesce(sum(source_row_count), 0) as mapped_rows
    from {{ ref('influencer_entities') }}
),
map_total as (
    select count(*) as mapped_rows
    from {{ ref('influencer_identity_map') }}
)

select entity_total.mapped_rows as entity_rows,
       map_total.mapped_rows as map_rows
from entity_total
cross join map_total
where entity_total.mapped_rows <> map_total.mapped_rows
