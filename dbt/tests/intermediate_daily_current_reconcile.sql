select 'shop' as source_name
where (select count(*) from {{ ref('int_shop_daily_current') }}) <>
      (select count(distinct metric_date) from {{ ref('stg_shop_analytics') }} where metric_date is not null)
union all
select 'campaign'
where (select count(*) from {{ ref('int_campaign_daily_current') }}) <>
      (select count(distinct metric_date) from {{ ref('stg_campaign') }} where metric_date is not null)
union all
select 'live'
where (select count(*) from {{ ref('int_live_daily_current') }}) <>
      (select count(distinct metric_date) from {{ ref('stg_live') }} where metric_date is not null)
union all
select 'product_card'
where (select count(*) from {{ ref('int_product_card_daily_current') }}) <>
      (select count(distinct metric_date) from {{ ref('stg_product_card') }} where metric_date is not null)
