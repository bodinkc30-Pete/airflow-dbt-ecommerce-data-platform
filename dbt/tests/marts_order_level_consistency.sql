with grouped as (
    select
        order_id,
        count(distinct coalesce(order_status, '__NULL__')) as order_status_values,
        count(distinct coalesce(order_substatus, '__NULL__')) as order_substatus_values,
        count(distinct coalesce(order_amount::text, '__NULL__')) as order_amount_values,
        count(distinct coalesce(created_at::text, '__NULL__')) as created_at_values,
        count(distinct coalesce(paid_at::text, '__NULL__')) as paid_at_values,
        count(distinct coalesce(shipping_fee_after_discount::text, '__NULL__')) as shipping_fee_values,
        count(distinct coalesce(original_shipping_fee::text, '__NULL__')) as original_shipping_fee_values,
        count(distinct coalesce(payment_platform_discount::text, '__NULL__')) as payment_discount_values,
        count(distinct coalesce(taxes::text, '__NULL__')) as taxes_values,
        count(distinct coalesce(fulfillment_type, '__NULL__')) as fulfillment_values,
        count(distinct coalesce(payment_method, '__NULL__')) as payment_method_values
    from {{ ref('int_order_items_current') }}
    group by order_id
)
select * from grouped
where order_status_values > 1
   or order_substatus_values > 1
   or order_amount_values > 1
   or created_at_values > 1
   or paid_at_values > 1
   or shipping_fee_values > 1
   or original_shipping_fee_values > 1
   or payment_discount_values > 1
   or taxes_values > 1
   or fulfillment_values > 1
   or payment_method_values > 1
