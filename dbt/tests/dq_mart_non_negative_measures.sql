{{ config(severity='error', tags=['dq_blocking']) }}

select 'fact_orders.order_amount' as check_name, order_key as row_key
from {{ ref('fact_orders') }} where order_amount < 0
union all
select 'fact_order_items.quantity', order_item_key
from {{ ref('fact_order_items') }} where quantity < 0
union all
select 'fact_order_items.returned_quantity', order_item_key
from {{ ref('fact_order_items') }} where returned_quantity < 0
union all
select 'fact_shop_daily.gmv', date_key::text
from {{ ref('fact_shop_daily') }} where gmv < 0
union all
select 'fact_campaign_daily.ad_cost', date_key::text
from {{ ref('fact_campaign_daily') }} where ad_cost < 0
union all
select 'fact_live_daily.live_attributed_gmv', date_key::text
from {{ ref('fact_live_daily') }} where live_attributed_gmv < 0
union all
select 'fact_product_card_daily.product_card_gmv', date_key::text
from {{ ref('fact_product_card_daily') }} where product_card_gmv < 0
union all
select 'fact_influencer_observation.follower_count', influencer_observation_key
from {{ ref('fact_influencer_observation') }} where follower_count < 0
union all
select 'fact_influencer_observation.budget', influencer_observation_key
from {{ ref('fact_influencer_observation') }} where budget < 0
