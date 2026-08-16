BEGIN;

-- ============================================================
-- Project 06
-- Raw Product Card Traffic Daily Physical Model
--
-- Source:
-- TikTok Product Card Traffic Stats Excel exports
--
-- Observed source grain:
-- 1 row = 1 shop-level Product Card traffic day
--
-- Current source characteristics:
-- - 16 source columns
-- - multiple files with identical schema
-- - no product_id in current export
-- - no sku_id in current export
-- - percentage metrics are preserved as source TEXT
-- - percentage values above 100% may be valid source behavior
--
-- Raw-layer principle:
-- Preserve source truth. Cleaning, percentage conversion,
-- numeric conversion, business interpretation, deduplication
-- across overlapping reporting windows, and quality warnings
-- belong downstream in ingestion/dbt layers.
-- ============================================================


CREATE TABLE IF NOT EXISTS raw.product_card_daily (

    -- --------------------------------------------------------
    -- Internal raw-row identity
    -- --------------------------------------------------------

    raw_product_card_daily_row_id
        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,


    -- --------------------------------------------------------
    -- Source columns: 1-8
    -- --------------------------------------------------------

    metric_date TEXT NOT NULL,
    product_card_views TEXT,
    product_card_clicks TEXT,
    customers TEXT,
    attributed_sku_orders TEXT,
    product_card_gmv TEXT,
    add_to_cart_to_payment_rate TEXT,
    viewers TEXT,


    -- --------------------------------------------------------
    -- Source columns: 9-16
    -- --------------------------------------------------------

    add_to_cart_clicks TEXT,
    unique_product_clicks TEXT,
    add_to_cart_customers TEXT,
    product_click_to_add_to_cart_rate TEXT,
    view_to_product_click_rate TEXT,
    view_to_payment_rate TEXT,
    product_click_to_payment_rate TEXT,
    content_attributed_gmv TEXT,


    -- --------------------------------------------------------
    -- Raw lineage metadata
    -- --------------------------------------------------------

    _source_file TEXT NOT NULL,
    _source_row_number BIGINT NOT NULL,
    _batch_id TEXT NOT NULL,
    _file_hash CHAR(64) NOT NULL,

    _ingested_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    _pipeline_run_id BIGINT NOT NULL,
    _ingestion_file_id BIGINT NOT NULL,


    -- --------------------------------------------------------
    -- Foreign keys to ingestion control plane
    -- --------------------------------------------------------

    CONSTRAINT fk_raw_product_card_daily_pipeline_run
        FOREIGN KEY (_pipeline_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_raw_product_card_daily_ingestion_file
        FOREIGN KEY (_ingestion_file_id)
        REFERENCES audit.ingestion_files (ingestion_file_id)
        ON DELETE RESTRICT,


    -- --------------------------------------------------------
    -- Raw-row identity inside one source file
    -- --------------------------------------------------------

    CONSTRAINT uq_raw_product_card_daily_file_source_row
        UNIQUE (
            _ingestion_file_id,
            _source_row_number
        ),


    -- --------------------------------------------------------
    -- Metadata validation
    -- --------------------------------------------------------

    CONSTRAINT chk_raw_product_card_daily_source_row_number
        CHECK (_source_row_number > 0),

    CONSTRAINT chk_raw_product_card_daily_file_hash_length
        CHECK (char_length(_file_hash) = 64)
);


-- ============================================================
-- Operational / lineage indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_raw_product_card_daily_metric_date
    ON raw.product_card_daily (metric_date);

CREATE INDEX IF NOT EXISTS idx_raw_product_card_daily_pipeline_run_id
    ON raw.product_card_daily (_pipeline_run_id);

CREATE INDEX IF NOT EXISTS idx_raw_product_card_daily_ingestion_file_id
    ON raw.product_card_daily (_ingestion_file_id);

CREATE INDEX IF NOT EXISTS idx_raw_product_card_daily_file_hash
    ON raw.product_card_daily (_file_hash);

CREATE INDEX IF NOT EXISTS idx_raw_product_card_daily_ingested_at
    ON raw.product_card_daily (_ingested_at DESC);


COMMIT;