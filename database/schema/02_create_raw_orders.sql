BEGIN;

-- ============================================================
-- Project 06
-- Raw Orders Physical Model
--
-- Source:
-- TikTok Seller Orders CSV
--
-- Grain:
-- 1 row = 1 order-SKU source line
--
-- Raw-layer principle:
-- Preserve source truth. Source columns remain TEXT.
-- Type conversion and normalization belong in dbt staging.
-- ============================================================


CREATE TABLE IF NOT EXISTS raw.orders (

    -- --------------------------------------------------------
    -- Internal raw-row identity
    -- --------------------------------------------------------

    raw_order_row_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,


    -- --------------------------------------------------------
    -- Source columns: 1-10
    -- --------------------------------------------------------

    order_id TEXT NOT NULL,
    order_status TEXT,
    order_substatus TEXT,
    cancelation_return_type TEXT,
    normal_or_pre_order TEXT,
    sku_id TEXT NOT NULL,
    seller_sku TEXT,
    product_name TEXT,
    variation TEXT,
    quantity TEXT,


    -- --------------------------------------------------------
    -- Source columns: 11-20
    -- --------------------------------------------------------

    sku_quantity_of_return TEXT,
    sku_unit_original_price TEXT,
    sku_subtotal_before_discount TEXT,
    sku_platform_discount TEXT,
    sku_seller_discount TEXT,
    sku_subtotal_after_discount TEXT,
    shipping_fee_after_discount TEXT,
    original_shipping_fee TEXT,
    shipping_fee_seller_discount TEXT,
    shipping_fee_platform_discount TEXT,


    -- --------------------------------------------------------
    -- Source columns: 21-30
    -- --------------------------------------------------------

    payment_platform_discount TEXT,
    taxes TEXT,
    order_amount TEXT,
    order_refund_amount TEXT,
    created_time TEXT,
    paid_time TEXT,
    rts_time TEXT,
    shipped_time TEXT,
    delivered_time TEXT,
    cancelled_time TEXT,


    -- --------------------------------------------------------
    -- Source columns: 31-40
    -- --------------------------------------------------------

    cancel_by TEXT,
    cancel_reason TEXT,
    fulfillment_type TEXT,
    warehouse_name TEXT,
    tracking_id TEXT,
    delivery_option TEXT,
    shipping_provider_name TEXT,
    buyer_message TEXT,
    buyer_username TEXT,
    recipient TEXT,


    -- --------------------------------------------------------
    -- Source columns: 41-50
    -- --------------------------------------------------------

    phone_number TEXT,
    zipcode TEXT,
    country TEXT,
    province TEXT,
    district TEXT,
    districts TEXT,
    detail_address TEXT,
    additional_address_information TEXT,
    payment_method TEXT,
    weight_kg TEXT,


    -- --------------------------------------------------------
    -- Source columns: 51-60
    -- --------------------------------------------------------

    product_category TEXT,
    package_id TEXT,
    seller_note TEXT,
    checked_status TEXT,
    checked_marked_by TEXT,
    order_channel TEXT,
    creator_handle TEXT,
    request_tax_invoice TEXT,
    tax_info_buyer_tax_id TEXT,
    tax_info_type TEXT,


    -- --------------------------------------------------------
    -- Source columns: 61-65
    -- --------------------------------------------------------

    tax_info_full_name_of_buyer TEXT,
    tax_info_email TEXT,
    tax_info_phone_number TEXT,
    tax_info_registered_address TEXT,
    tax_info_address_type TEXT,


    -- --------------------------------------------------------
    -- Raw lineage metadata
    -- --------------------------------------------------------

    _source_file TEXT NOT NULL,
    _source_row_number BIGINT NOT NULL,
    _batch_id TEXT NOT NULL,
    _file_hash CHAR(64) NOT NULL,
    _ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    _pipeline_run_id BIGINT NOT NULL,
    _ingestion_file_id BIGINT NOT NULL,


    -- --------------------------------------------------------
    -- Foreign keys to ingestion control plane
    -- --------------------------------------------------------

    CONSTRAINT fk_raw_orders_pipeline_run
        FOREIGN KEY (_pipeline_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_raw_orders_ingestion_file
        FOREIGN KEY (_ingestion_file_id)
        REFERENCES audit.ingestion_files (ingestion_file_id)
        ON DELETE RESTRICT,


    -- --------------------------------------------------------
    -- Raw-row identity within one source file
    -- --------------------------------------------------------

    CONSTRAINT uq_raw_orders_file_source_row
        UNIQUE (_ingestion_file_id, _source_row_number),


    -- --------------------------------------------------------
    -- Basic metadata validation
    -- --------------------------------------------------------

    CONSTRAINT chk_raw_orders_source_row_number
        CHECK (_source_row_number > 0),

    CONSTRAINT chk_raw_orders_file_hash_length
        CHECK (char_length(_file_hash) = 64)
);


-- ============================================================
-- Operational / lineage indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_raw_orders_order_id
    ON raw.orders (order_id);

CREATE INDEX IF NOT EXISTS idx_raw_orders_sku_id
    ON raw.orders (sku_id);

CREATE INDEX IF NOT EXISTS idx_raw_orders_order_sku
    ON raw.orders (order_id, sku_id);

CREATE INDEX IF NOT EXISTS idx_raw_orders_pipeline_run_id
    ON raw.orders (_pipeline_run_id);

CREATE INDEX IF NOT EXISTS idx_raw_orders_ingestion_file_id
    ON raw.orders (_ingestion_file_id);

CREATE INDEX IF NOT EXISTS idx_raw_orders_file_hash
    ON raw.orders (_file_hash);

CREATE INDEX IF NOT EXISTS idx_raw_orders_ingested_at
    ON raw.orders (_ingested_at DESC);


COMMIT;