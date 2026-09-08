with skus as (
    select count(*) as row_count from {{ ref('int_skus_current') }}
),
catalog as (
    select count(*) as row_count from {{ ref('int_product_sku_catalog') }}
)
select 1
from skus cross join catalog
where skus.row_count <> catalog.row_count
