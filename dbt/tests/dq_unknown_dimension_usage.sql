{{ config(severity='warn', tags=['dq_warning']) }}

select
    order_item_key,
    case when sku_key = 'sku_unknown' then 1 else 0 end as unknown_sku,
    case when product_key = 'product_unknown' then 1 else 0 end as unknown_product,
    case when influencer_key = 'influencer_unknown' then 1 else 0 end as unknown_influencer,
    case when created_date_key = 0 then 1 else 0 end as unknown_created_date
from {{ ref('fact_order_items') }}
where sku_key = 'sku_unknown'
   or product_key = 'product_unknown'
   or influencer_key = 'influencer_unknown'
   or created_date_key = 0
