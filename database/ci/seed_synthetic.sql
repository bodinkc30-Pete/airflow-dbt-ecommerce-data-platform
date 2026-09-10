BEGIN;

INSERT INTO audit.ingestion_runs (
    pipeline_name, run_type, started_at, finished_at, status,
    files_discovered, files_processed, files_failed,
    rows_discovered, rows_loaded, rows_rejected
)
SELECT
    'ci_synthetic_seed', 'test', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'success',
    8, 8, 0, 8, 8, 0
WHERE NOT EXISTS (
    SELECT 1 FROM audit.ingestion_runs WHERE pipeline_name = 'ci_synthetic_seed'
);

WITH seed_run AS (
    SELECT ingestion_run_id
    FROM audit.ingestion_runs
    WHERE pipeline_name = 'ci_synthetic_seed'
    ORDER BY ingestion_run_id
    LIMIT 1
), seed_files(source_name, file_name, file_hash_sha256) AS (
    VALUES
        ('orders', 'ci_synthetic_orders.csv', repeat('1', 64)::char(64)),
        ('shop_daily', 'ci_synthetic_shop_daily.csv', repeat('2', 64)::char(64)),
        ('campaign_daily', 'ci_synthetic_campaign_daily.csv', repeat('3', 64)::char(64)),
        ('live_daily', 'ci_synthetic_live_daily.csv', repeat('4', 64)::char(64)),
        ('product_card_daily', 'ci_synthetic_product_card_daily.csv', repeat('5', 64)::char(64)),
        ('products', 'ci_synthetic_products.csv', repeat('6', 64)::char(64)),
        ('skus', 'ci_synthetic_skus.csv', repeat('7', 64)::char(64)),
        ('influencer_roster', 'ci_synthetic_influencer.csv', repeat('8', 64)::char(64))
)
INSERT INTO audit.ingestion_files (
    ingestion_run_id, source_name, file_name, file_path, file_hash_sha256,
    status, rows_discovered, rows_loaded, rows_rejected
)
SELECT
    seed_run.ingestion_run_id,
    seed_files.source_name,
    seed_files.file_name,
    'data/demo/' || seed_files.file_name,
    seed_files.file_hash_sha256,
    'success', 1, 1, 0
FROM seed_run CROSS JOIN seed_files
ON CONFLICT (source_name, file_hash_sha256) DO NOTHING;

INSERT INTO raw.products (
    product_id, product_name, gmv_tier, product_status, source_payload,
    _source_file, _source_row_number, _batch_id, _file_hash,
    _ingested_at, _pipeline_run_id, _ingestion_file_id
)
SELECT
    'CI-PRODUCT-001', 'CI Synthetic Product', 'A', 'ACTIVE', '{}'::jsonb,
    'ci_synthetic_products.csv', 1, 'ci_synthetic_batch', repeat('6', 64)::char(64),
    CURRENT_TIMESTAMP,
    (SELECT ingestion_run_id FROM audit.ingestion_runs WHERE pipeline_name = 'ci_synthetic_seed' ORDER BY ingestion_run_id LIMIT 1),
    (SELECT ingestion_file_id FROM audit.ingestion_files WHERE source_name = 'products' AND file_hash_sha256 = repeat('6', 64)::char(64))
WHERE NOT EXISTS (
    SELECT 1 FROM raw.products WHERE product_id = 'CI-PRODUCT-001'
);

INSERT INTO raw.skus (
    sku_id, product_id, sku_name, sku_status, gmv, sku_orders, items_sold,
    _source_file, _source_row_number, _batch_id, _file_hash,
    _ingested_at, _pipeline_run_id, _ingestion_file_id
)
SELECT
    'CI-SKU-001', 'CI-PRODUCT-001', 'CI Synthetic SKU', 'ACTIVE', '100.00', '1', '1',
    'ci_synthetic_skus.csv', 1, 'ci_synthetic_batch', repeat('7', 64)::char(64),
    CURRENT_TIMESTAMP,
    (SELECT ingestion_run_id FROM audit.ingestion_runs WHERE pipeline_name = 'ci_synthetic_seed' ORDER BY ingestion_run_id LIMIT 1),
    (SELECT ingestion_file_id FROM audit.ingestion_files WHERE source_name = 'skus' AND file_hash_sha256 = repeat('7', 64)::char(64))
WHERE NOT EXISTS (SELECT 1 FROM raw.skus WHERE sku_id = 'CI-SKU-001');

INSERT INTO raw.orders (
    order_id, order_status, sku_id, seller_sku, product_name, quantity,
    sku_quantity_of_return, sku_unit_original_price, sku_subtotal_before_discount,
    sku_subtotal_after_discount, order_amount, created_time, paid_time,
    creator_handle, _source_file, _source_row_number, _batch_id, _file_hash,
    _ingested_at, _pipeline_run_id, _ingestion_file_id
)
SELECT
    'CI-ORDER-001', 'COMPLETED', 'CI-SKU-001', 'CI-SELLER-SKU-001',
    'CI Synthetic Product', '1', '0', '100.00', '100.00', '100.00', '100.00',
    to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'),
    to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'),
    'ci_synthetic_creator', 'ci_synthetic_orders.csv', 1,
    'ci_synthetic_batch', repeat('1', 64)::char(64), CURRENT_TIMESTAMP,
    (SELECT ingestion_run_id FROM audit.ingestion_runs WHERE pipeline_name = 'ci_synthetic_seed' ORDER BY ingestion_run_id LIMIT 1),
    (SELECT ingestion_file_id FROM audit.ingestion_files WHERE source_name = 'orders' AND file_hash_sha256 = repeat('1', 64)::char(64))
WHERE NOT EXISTS (
    SELECT 1 FROM raw.orders WHERE order_id = 'CI-ORDER-001' AND sku_id = 'CI-SKU-001'
);

INSERT INTO raw.shop_daily (
    metric_date, gmv, orders, customers, items_sold, refunds, sku_orders,
    gross_revenue, page_views, visitors, conversion_rate,
    _source_file, _source_row_number, _batch_id, _file_hash,
    _ingested_at, _pipeline_run_id, _ingestion_file_id
)
SELECT
    CURRENT_DATE::text, '100.00', '1', '1', '1', '0.00', '1',
    '100.00', '10', '5', '0.20',
    'ci_synthetic_shop_daily.csv', 1, 'ci_synthetic_batch', repeat('2', 64)::char(64),
    CURRENT_TIMESTAMP,
    (SELECT ingestion_run_id FROM audit.ingestion_runs WHERE pipeline_name = 'ci_synthetic_seed' ORDER BY ingestion_run_id LIMIT 1),
    (SELECT ingestion_file_id FROM audit.ingestion_files WHERE source_name = 'shop_daily' AND file_hash_sha256 = repeat('2', 64)::char(64))
WHERE NOT EXISTS (
    SELECT 1 FROM raw.shop_daily WHERE _file_hash = repeat('2', 64)::char(64) AND _source_row_number = 1
);

INSERT INTO raw.campaign_daily (
    metric_date, ad_cost, sku_orders, cost_per_order, gross_revenue, roi, currency,
    _source_file, _source_row_number, _batch_id, _file_hash,
    _ingested_at, _pipeline_run_id, _ingestion_file_id
)
SELECT
    CURRENT_DATE::text, '20.00', '1', '20.00', '100.00', '5.00', 'THB',
    'ci_synthetic_campaign_daily.csv', 1, 'ci_synthetic_batch', repeat('3', 64)::char(64),
    CURRENT_TIMESTAMP,
    (SELECT ingestion_run_id FROM audit.ingestion_runs WHERE pipeline_name = 'ci_synthetic_seed' ORDER BY ingestion_run_id LIMIT 1),
    (SELECT ingestion_file_id FROM audit.ingestion_files WHERE source_name = 'campaign_daily' AND file_hash_sha256 = repeat('3', 64)::char(64))
WHERE NOT EXISTS (
    SELECT 1 FROM raw.campaign_daily WHERE _file_hash = repeat('3', 64)::char(64) AND _source_row_number = 1
);

INSERT INTO raw.live_daily (
    metric_date, live_attributed_gmv, live_direct_gmv, live_indirect_gmv,
    live_stream_count, gmv_generating_live_stream_count,
    live_attributed_items_sold, attributed_sku_orders, live_click_through_rate,
    live_views, _source_file, _source_row_number, _batch_id, _file_hash,
    _ingested_at, _pipeline_run_id, _ingestion_file_id
)
SELECT
    CURRENT_DATE::text, '50.00', '40.00', '10.00', '1', '1', '1', '1', '0.10', '20',
    'ci_synthetic_live_daily.csv', 1, 'ci_synthetic_batch', repeat('4', 64)::char(64),
    CURRENT_TIMESTAMP,
    (SELECT ingestion_run_id FROM audit.ingestion_runs WHERE pipeline_name = 'ci_synthetic_seed' ORDER BY ingestion_run_id LIMIT 1),
    (SELECT ingestion_file_id FROM audit.ingestion_files WHERE source_name = 'live_daily' AND file_hash_sha256 = repeat('4', 64)::char(64))
WHERE NOT EXISTS (
    SELECT 1 FROM raw.live_daily WHERE _file_hash = repeat('4', 64)::char(64) AND _source_row_number = 1
);

INSERT INTO raw.product_card_daily (
    metric_date, product_card_views, product_card_clicks, customers,
    attributed_sku_orders, product_card_gmv, add_to_cart_to_payment_rate,
    viewers, add_to_cart_clicks, unique_product_clicks, add_to_cart_customers,
    product_click_to_add_to_cart_rate, view_to_product_click_rate,
    view_to_payment_rate, product_click_to_payment_rate,
    _source_file, _source_row_number, _batch_id, _file_hash,
    _ingested_at, _pipeline_run_id, _ingestion_file_id
)
SELECT
    CURRENT_DATE::text, '20', '10', '1', '1', '100.00', '0.50',
    '10', '5', '8', '4', '0.50', '0.50', '0.10', '0.20',
    'ci_synthetic_product_card_daily.csv', 1, 'ci_synthetic_batch', repeat('5', 64)::char(64),
    CURRENT_TIMESTAMP,
    (SELECT ingestion_run_id FROM audit.ingestion_runs WHERE pipeline_name = 'ci_synthetic_seed' ORDER BY ingestion_run_id LIMIT 1),
    (SELECT ingestion_file_id FROM audit.ingestion_files WHERE source_name = 'product_card_daily' AND file_hash_sha256 = repeat('5', 64)::char(64))
WHERE NOT EXISTS (
    SELECT 1 FROM raw.product_card_daily WHERE _file_hash = repeat('5', 64)::char(64) AND _source_row_number = 1
);

INSERT INTO raw.influencer_roster (
    influencer_name, follower_count, engagement_rate, budget, source_payload,
    _source_file, _source_row_number, _batch_id, _file_hash,
    _ingested_at, _pipeline_run_id, _ingestion_file_id
)
SELECT
    'ci_synthetic_creator', '1000', '0.10', '100.00', '{}'::jsonb,
    'ci_synthetic_influencer.csv', 1, 'ci_synthetic_batch', repeat('8', 64)::char(64),
    CURRENT_TIMESTAMP,
    (SELECT ingestion_run_id FROM audit.ingestion_runs WHERE pipeline_name = 'ci_synthetic_seed' ORDER BY ingestion_run_id LIMIT 1),
    (SELECT ingestion_file_id FROM audit.ingestion_files WHERE source_name = 'influencer_roster' AND file_hash_sha256 = repeat('8', 64)::char(64))
WHERE NOT EXISTS (
    SELECT 1 FROM raw.influencer_roster WHERE influencer_name = 'ci_synthetic_creator'
);

COMMIT;
