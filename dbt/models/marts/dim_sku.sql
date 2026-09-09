with catalog as (
    select * from {{ ref('int_product_sku_catalog') }}
)

select
    'sku_unknown'::text as sku_key,
    null::text as sku_id,
    'product_unknown'::text as product_key,
    null::text as product_id,
    'Unknown SKU'::text as sku_name,
    'unknown'::text as sku_status,
    null::numeric as sku_gmv,
    null::bigint as sku_orders,
    null::bigint as sku_items_sold,
    'unknown_product'::text as product_match_status,
    0::bigint as sku_snapshot_observation_count,
    0::bigint as sku_source_file_count,
    null::timestamptz as last_seen_at
union all
select
    'sku_v1_' || md5(sku_id) as sku_key,
    sku_id,
    case when product_match_status = 'matched_product'
        then 'product_v1_' || md5(product_id)
        else 'product_unknown' end as product_key,
    product_id,
    sku_name,
    sku_status,
    sku_gmv,
    sku_orders,
    sku_items_sold,
    product_match_status,
    sku_snapshot_observation_count,
    sku_source_file_count,
    sku_ingested_at as last_seen_at
from catalog
