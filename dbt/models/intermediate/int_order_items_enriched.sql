with orders as (
    select * from {{ ref('int_order_items_current') }}
),

catalog as (
    select * from {{ ref('int_product_sku_catalog') }}
),

creator_bridge as (
    select * from {{ ref('int_creator_identity_bridge') }}
)

select
    orders.*,
    catalog.product_id as catalog_product_id,
    catalog.sku_name as catalog_sku_name,
    catalog.sku_status as catalog_sku_status,
    catalog.product_name as catalog_product_name,
    catalog.product_status as catalog_product_status,
    catalog.gmv_tier as catalog_gmv_tier,
    case
        when catalog.sku_id is null then 'unmatched_sku'
        else 'matched_sku'
    end as sku_match_status,
    coalesce(catalog.product_match_status, 'not_evaluated') as product_match_status,
    creator_bridge.influencer_entity_key,
    creator_bridge.identity_method as creator_identity_method,
    creator_bridge.identity_confidence as creator_identity_confidence,
    creator_bridge.influencer_requires_manual_review,
    case
        when orders.creator_handle is null then 'no_creator'
        else creator_bridge.creator_identity_match_status
    end as creator_identity_match_status
from orders
left join catalog
    on orders.sku_id = catalog.sku_id
left join creator_bridge
    on {{ normalize_influencer_identity('orders.creator_handle') }}
     = creator_bridge.normalized_creator_handle
