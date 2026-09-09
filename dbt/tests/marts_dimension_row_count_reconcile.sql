with checks as (
    select 'product' as dimension,
        (select count(*) + 1 from {{ ref('int_products_current') }}) as expected,
        (select count(*) from {{ ref('dim_product') }}) as actual
    union all
    select 'sku',
        (select count(*) + 1 from {{ ref('int_product_sku_catalog') }}),
        (select count(*) from {{ ref('dim_sku') }})
    union all
    select 'influencer',
        (select count(*) + 1 from {{ ref('influencer_entities') }}),
        (select count(*) from {{ ref('dim_influencer') }})
)
select * from checks where expected <> actual
