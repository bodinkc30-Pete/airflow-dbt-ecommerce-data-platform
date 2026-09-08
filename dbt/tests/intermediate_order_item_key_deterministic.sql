select order_item_key
from {{ ref('int_order_items_current') }}
where order_item_key <> 'order_item_v1_' || md5(order_id || '|' || sku_id)
