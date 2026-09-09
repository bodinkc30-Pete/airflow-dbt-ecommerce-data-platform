select *
from {{ ref('fact_order_items') }}
where (sku_match_status = 'unmatched_sku' and sku_key <> 'sku_unknown')
   or (sku_match_status = 'matched_sku' and sku_key = 'sku_unknown')
   or (product_match_status <> 'matched_product' and product_key <> 'product_unknown')
   or (product_match_status = 'matched_product' and product_key = 'product_unknown')
   or (creator_identity_match_status <> 'matched_influencer_entity'
       and influencer_key <> 'influencer_unknown')
   or (creator_identity_match_status = 'matched_influencer_entity'
       and influencer_key = 'influencer_unknown')
