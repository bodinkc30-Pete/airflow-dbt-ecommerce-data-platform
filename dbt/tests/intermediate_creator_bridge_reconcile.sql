with expected as (
    select count(distinct {{ normalize_influencer_identity('creator_handle') }}) as row_count
    from {{ ref('int_order_items_current') }}
    where creator_handle is not null
),
actual as (
    select count(*) as row_count from {{ ref('int_creator_identity_bridge') }}
)
select 1
from expected cross join actual
where expected.row_count <> actual.row_count
