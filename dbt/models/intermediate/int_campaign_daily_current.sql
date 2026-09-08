with source as (
    select * from {{ ref('stg_campaign') }}
    where metric_date is not null
),

stats as (
    select
        metric_date,
        count(*) as source_observation_count,
        count(distinct ingestion_file_id) as source_file_count
    from source
    group by metric_date
),

latest as (
    select distinct on (metric_date) *
    from source
    order by
        metric_date,
        ingested_at desc,
        pipeline_run_id desc,
        ingestion_file_id desc,
        campaign_daily_row_id desc
)

select
    latest.*,
    stats.source_observation_count,
    stats.source_file_count
from latest
join stats using (metric_date)
