with checks as (
    select 'orders' as fact, (select count(*) from {{ ref('int_order_items_enriched') }}) expected, (select count(*) from {{ ref('fact_order_items') }}) actual
    union all
    select 'order_headers', (select count(distinct order_id) from {{ ref('int_order_items_current') }}), (select count(*) from {{ ref('fact_orders') }})
    union all
    select 'shop', (select count(*) from {{ ref('int_shop_daily_current') }}), (select count(*) from {{ ref('fact_shop_daily') }})
    union all
    select 'campaign', (select count(*) from {{ ref('int_campaign_daily_current') }}), (select count(*) from {{ ref('fact_campaign_daily') }})
    union all
    select 'live', (select count(*) from {{ ref('int_live_daily_current') }}), (select count(*) from {{ ref('fact_live_daily') }})
    union all
    select 'product_card', (select count(*) from {{ ref('int_product_card_daily_current') }}), (select count(*) from {{ ref('fact_product_card_daily') }})
    union all
    select 'influencer_observation', (select count(*) from {{ ref('influencer_identity_map') }}), (select count(*) from {{ ref('fact_influencer_observation') }})
)
select * from checks where expected <> actual
