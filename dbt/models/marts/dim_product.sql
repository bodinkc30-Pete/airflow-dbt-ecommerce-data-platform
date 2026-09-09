with current_products as (
    select * from {{ ref('int_products_current') }}
)

select
    'product_unknown'::text as product_key,
    null::text as product_id,
    'Unknown Product'::text as product_name,
    null::text as gmv_tier,
    'unknown'::text as product_status,
    0::bigint as snapshot_observation_count,
    0::bigint as source_file_count,
    null::timestamptz as last_seen_at
union all
select
    'product_v1_' || md5(product_id) as product_key,
    product_id,
    product_name,
    gmv_tier,
    product_status,
    snapshot_observation_count,
    source_file_count,
    ingested_at as last_seen_at
from current_products
