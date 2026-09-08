with dates as (
    select metric_date from {{ ref('int_shop_daily_current') }}
    union
    select metric_date from {{ ref('int_campaign_daily_current') }}
    union
    select metric_date from {{ ref('int_live_daily_current') }}
    union
    select metric_date from {{ ref('int_product_card_daily_current') }}
),

shop as (
    select * from {{ ref('int_shop_daily_current') }}
),

campaign as (
    select * from {{ ref('int_campaign_daily_current') }}
),

live as (
    select * from {{ ref('int_live_daily_current') }}
),

product_card as (
    select * from {{ ref('int_product_card_daily_current') }}
)

select
    dates.metric_date,
    shop.gmv as shop_gmv,
    shop.orders as shop_orders,
    shop.customers as shop_customers,
    shop.items_sold as shop_items_sold,
    shop.refunds as shop_refunds,
    shop.sku_orders as shop_sku_orders,
    shop.gross_revenue as shop_gross_revenue,
    shop.page_views as shop_page_views,
    shop.visitors as shop_visitors,
    shop.conversion_rate as shop_conversion_rate,
    shop.average_order_value as shop_average_order_value,
    shop.source_observation_count as shop_source_observation_count,
    campaign.ad_cost as campaign_ad_cost,
    campaign.sku_orders as campaign_sku_orders,
    campaign.cost_per_order as campaign_cost_per_order,
    campaign.gross_revenue as campaign_gross_revenue,
    campaign.roi as campaign_roi,
    campaign.currency as campaign_currency,
    campaign.source_observation_count as campaign_source_observation_count,
    live.live_attributed_gmv,
    live.live_direct_gmv,
    live.live_indirect_gmv,
    live.live_stream_count,
    live.attributed_sku_orders as live_attributed_sku_orders,
    live.live_direct_sku_orders,
    live.live_indirect_sku_orders,
    live.live_click_through_rate,
    live.live_views,
    live.average_live_watch_duration,
    live.source_observation_count as live_source_observation_count,
    product_card.product_card_views,
    product_card.product_card_clicks,
    product_card.customers as product_card_customers,
    product_card.attributed_sku_orders as product_card_attributed_sku_orders,
    product_card.product_card_gmv,
    product_card.add_to_cart_to_payment_rate,
    product_card.viewers as product_card_viewers,
    product_card.add_to_cart_clicks,
    product_card.unique_product_clicks as product_card_unique_product_clicks,
    product_card.add_to_cart_customers,
    product_card.product_click_to_add_to_cart_rate,
    product_card.view_to_product_click_rate,
    product_card.view_to_payment_rate,
    product_card.product_click_to_payment_rate,
    product_card.content_attributed_gmv,
    product_card.source_observation_count as product_card_source_observation_count,
    (shop.metric_date is not null) as has_shop_metrics,
    (campaign.metric_date is not null) as has_campaign_metrics,
    (live.metric_date is not null) as has_live_metrics,
    (product_card.metric_date is not null) as has_product_card_metrics
from dates
left join shop using (metric_date)
left join campaign using (metric_date)
left join live using (metric_date)
left join product_card using (metric_date)
