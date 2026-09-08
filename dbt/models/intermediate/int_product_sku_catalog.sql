with skus as (
    select * from {{ ref('int_skus_current') }}
),

products as (
    select * from {{ ref('int_products_current') }}
)

select
    skus.sku_id,
    skus.product_id,
    skus.sku_name,
    skus.sku_status,
    skus.gmv as sku_gmv,
    skus.sku_orders,
    skus.items_sold as sku_items_sold,
    products.product_name,
    products.gmv_tier,
    products.product_status,
    case
        when products.product_id is null then 'unmatched_product'
        else 'matched_product'
    end as product_match_status,
    skus.snapshot_observation_count as sku_snapshot_observation_count,
    skus.source_file_count as sku_source_file_count,
    products.snapshot_observation_count as product_snapshot_observation_count,
    products.source_file_count as product_source_file_count,
    skus.sku_row_id,
    products.product_row_id,
    skus.ingested_at as sku_ingested_at,
    products.ingested_at as product_ingested_at
from skus
left join products using (product_id)
