select
    order_id,
    sku_id,
    count(*) as row_count
from {{ ref('int_order_items_current') }}
group by order_id, sku_id
having count(*) > 1
