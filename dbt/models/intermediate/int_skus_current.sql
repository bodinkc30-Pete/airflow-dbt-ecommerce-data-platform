with source as (
    select * from {{ ref('stg_skus') }}
    where sku_id is not null
),

stats as (
    select
        sku_id,
        count(*) as snapshot_observation_count,
        count(distinct ingestion_file_id) as source_file_count
    from source
    group by sku_id
),

latest as (
    select distinct on (sku_id) *
    from source
    order by
        sku_id,
        ingested_at desc,
        pipeline_run_id desc,
        ingestion_file_id desc,
        sku_row_id desc
)

select
    latest.*,
    stats.snapshot_observation_count,
    stats.source_file_count
from latest
join stats using (sku_id)
