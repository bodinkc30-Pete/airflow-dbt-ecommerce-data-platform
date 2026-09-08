with source as (
    select * from {{ ref('stg_orders') }}
    where order_id is not null
      and sku_id is not null
),

stats as (
    select
        order_id,
        sku_id,
        count(*) as source_observation_count,
        count(distinct ingestion_file_id) as source_file_count
    from source
    group by order_id, sku_id
),

latest as (
    select distinct on (order_id, sku_id) *
    from source
    order by
        order_id,
        sku_id,
        ingested_at desc,
        pipeline_run_id desc,
        ingestion_file_id desc,
        order_row_id desc
)

select
    'order_item_v1_' || md5(order_id || '|' || sku_id) as order_item_key,
    latest.*,
    stats.source_observation_count,
    stats.source_file_count
from latest
join stats using (order_id, sku_id)
