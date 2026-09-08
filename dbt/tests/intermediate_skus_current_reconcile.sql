with expected as (
    select count(distinct sku_id) as row_count
    from {{ ref('stg_skus') }}
    where sku_id is not null
),
actual as (
    select count(*) as row_count from {{ ref('int_skus_current') }}
)
select 1
from expected cross join actual
where expected.row_count <> actual.row_count
