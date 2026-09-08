with counts as (
    select
        (select count(*) from {{ ref('stg_influencer') }}) as staging_rows,
        (select count(*) from {{ ref('influencer_identity_map') }}) as mapped_rows
)

select *
from counts
where staging_rows <> mapped_rows
