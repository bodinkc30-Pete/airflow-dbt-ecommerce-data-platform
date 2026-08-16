BEGIN;

-- ============================================================
-- Project 06
-- Raw Shop Analytics Daily Physical Model
--
-- Source:
-- TikTok Shop Analytics - Key Metrics Excel export
--
-- Grain:
-- 1 row = 1 shop-day source row
--
-- Raw-layer principle:
-- Preserve source truth. Source metric columns remain TEXT.
-- Cleaning, NULL normalization, type conversion, and business
-- logic belong in dbt staging.
-- ============================================================


CREATE TABLE IF NOT EXISTS raw.shop_daily (

    -- --------------------------------------------------------
    -- Internal raw-row identity
    -- --------------------------------------------------------

    raw_shop_daily_row_id
        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,


    -- --------------------------------------------------------
    -- Source columns: 1-10
    -- --------------------------------------------------------

    metric_date TEXT NOT NULL,
    gmv TEXT,
    orders TEXT,
    customers TEXT,
    items_sold TEXT,
    refunds TEXT,
    sku_orders TEXT,
    gross_revenue TEXT,
    page_views TEXT,
    visitors TEXT,


    -- --------------------------------------------------------
    -- Source columns: 11-20
    -- --------------------------------------------------------

    conversion_rate TEXT,
    product_impressions TEXT,
    unique_product_impressions TEXT,
    product_clicks TEXT,
    unique_product_clicks TEXT,
    aov TEXT,

    creator_live_attributed_gmv TEXT,
    creator_live_direct_gmv TEXT,
    creator_live_indirect_gmv TEXT,

    linked_account_live_gmv TEXT,


    -- --------------------------------------------------------
    -- Source columns: 21-28
    -- --------------------------------------------------------

    seller_live_direct_gmv TEXT,
    seller_live_indirect_gmv TEXT,

    affiliate_video_attributed_gmv TEXT,
    creator_video_direct_gmv TEXT,
    creator_video_indirect_gmv TEXT,

    linked_account_video_gmv TEXT,

    seller_video_direct_gmv TEXT,
    seller_video_indirect_gmv TEXT,


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

    CONSTRAINT fk_raw_shop_daily_pipeline_run
        FOREIGN KEY (_pipeline_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_raw_shop_daily_ingestion_file
        FOREIGN KEY (_ingestion_file_id)
        REFERENCES audit.ingestion_files (ingestion_file_id)
        ON DELETE RESTRICT,


    -- --------------------------------------------------------
    -- Raw-row identity inside one source file
    -- --------------------------------------------------------

    CONSTRAINT uq_raw_shop_daily_file_source_row
        UNIQUE (
            _ingestion_file_id,
            _source_row_number
        ),


    -- --------------------------------------------------------
    -- Metadata validation
    -- --------------------------------------------------------

    CONSTRAINT chk_raw_shop_daily_source_row_number
        CHECK (_source_row_number > 0),

    CONSTRAINT chk_raw_shop_daily_file_hash_length
        CHECK (char_length(_file_hash) = 64)
);


-- ============================================================
-- Operational / lineage indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_raw_shop_daily_metric_date
    ON raw.shop_daily (metric_date);

CREATE INDEX IF NOT EXISTS idx_raw_shop_daily_pipeline_run_id
    ON raw.shop_daily (_pipeline_run_id);

CREATE INDEX IF NOT EXISTS idx_raw_shop_daily_ingestion_file_id
    ON raw.shop_daily (_ingestion_file_id);

CREATE INDEX IF NOT EXISTS idx_raw_shop_daily_file_hash
    ON raw.shop_daily (_file_hash);

CREATE INDEX IF NOT EXISTS idx_raw_shop_daily_ingested_at
    ON raw.shop_daily (_ingested_at DESC);


COMMIT;