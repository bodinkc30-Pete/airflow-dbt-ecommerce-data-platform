select order_item_key
from {{ ref('int_order_items_current') }}
where order_item_key !~ '^order_item_v1_[0-9a-f]{32}$'
