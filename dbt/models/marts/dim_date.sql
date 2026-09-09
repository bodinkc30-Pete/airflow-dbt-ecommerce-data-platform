with date_candidates as (
    select created_at::date as date_day from {{ ref('int_order_items_current') }} where created_at is not null
    union all
    select paid_at::date from {{ ref('int_order_items_current') }} where paid_at is not null
    union all
    select ready_to_ship_at::date from {{ ref('int_order_items_current') }} where ready_to_ship_at is not null
    union all
    select shipped_at::date from {{ ref('int_order_items_current') }} where shipped_at is not null
    union all
    select delivered_at::date from {{ ref('int_order_items_current') }} where delivered_at is not null
    union all
    select cancelled_at::date from {{ ref('int_order_items_current') }} where cancelled_at is not null
    union all
    select metric_date from {{ ref('int_daily_performance') }}
    union all
    select ingested_at::date from {{ ref('influencer_identity_map') }} where ingested_at is not null
),

bounds as (
    select
        coalesce(min(date_day), current_date) as min_date,
        coalesce(max(date_day), current_date) as max_date
    from date_candidates
),

calendar as (
    select generated::date as date_day
    from bounds
    cross join lateral generate_series(min_date, max_date, interval '1 day') generated
)
select
    0::integer as date_key,
    null::date as date_day,
    0::integer as calendar_year,
    0::integer as calendar_quarter,
    0::integer as calendar_month,
    'Unknown'::text as month_name,
    0::integer as day_of_month,
    0::integer as day_of_week,
    'Unknown'::text as day_name,
    0::integer as iso_week,
    null::boolean as is_weekend
union all
select
    to_char(date_day, 'YYYYMMDD')::integer as date_key,
    date_day,
    extract(year from date_day)::integer as calendar_year,
    extract(quarter from date_day)::integer as calendar_quarter,
    extract(month from date_day)::integer as calendar_month,
    trim(to_char(date_day, 'Month')) as month_name,
    extract(day from date_day)::integer as day_of_month,
    extract(isodow from date_day)::integer as day_of_week,
    trim(to_char(date_day, 'Day')) as day_name,
    extract(week from date_day)::integer as iso_week,
    extract(isodow from date_day) in (6, 7) as is_weekend
from calendar
