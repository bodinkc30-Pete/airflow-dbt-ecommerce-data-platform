with source as (
    select * from {{ ref('stg_products') }}
    where product_id is not null
),

stats as (
    select
        product_id,
        count(*) as snapshot_observation_count,
        count(distinct ingestion_file_id) as source_file_count
    from source
    group by product_id
),

latest as (
    select distinct on (product_id) *
    from source
    order by
        product_id,
        ingested_at desc,
        pipeline_run_id desc,
        ingestion_file_id desc,
        product_row_id desc
)

select
    latest.*,
    stats.snapshot_observation_count,
    stats.source_file_count
from latest
join stats using (product_id)
