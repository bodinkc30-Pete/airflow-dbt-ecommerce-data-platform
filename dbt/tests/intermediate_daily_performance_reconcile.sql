with expected_dates as (
    select metric_date from {{ ref('int_shop_daily_current') }}
    union
    select metric_date from {{ ref('int_campaign_daily_current') }}
    union
    select metric_date from {{ ref('int_live_daily_current') }}
    union
    select metric_date from {{ ref('int_product_card_daily_current') }}
),
expected as (
    select count(*) as row_count from expected_dates
),
actual as (
    select count(*) as row_count from {{ ref('int_daily_performance') }}
)
select 1
from expected cross join actual
where expected.row_count <> actual.row_count
