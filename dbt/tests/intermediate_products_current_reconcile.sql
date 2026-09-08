with expected as (
    select count(distinct product_id) as row_count
    from {{ ref('stg_products') }}
    where product_id is not null
),
actual as (
    select count(*) as row_count from {{ ref('int_products_current') }}
)
select 1
from expected cross join actual
where expected.row_count <> actual.row_count
