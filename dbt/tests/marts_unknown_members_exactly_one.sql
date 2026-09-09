with checks as (
    select 'date' as member, count(*) as actual from {{ ref('dim_date') }} where date_key = 0
    union all
    select 'product', count(*) from {{ ref('dim_product') }} where product_key = 'product_unknown'
    union all
    select 'sku', count(*) from {{ ref('dim_sku') }} where sku_key = 'sku_unknown'
    union all
    select 'influencer', count(*) from {{ ref('dim_influencer') }} where influencer_key = 'influencer_unknown'
)
select * from checks where actual <> 1
