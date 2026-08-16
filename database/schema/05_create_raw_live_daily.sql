BEGIN;

-- ============================================================
-- Project 06
-- Raw LIVE Performance Daily Physical Model
--
-- Source:
-- TikTok LIVE Performance Core Stats Excel export
--
-- Observed source grain:
-- 1 row = 1 LIVE performance day
--
-- Current source characteristics:
-- - 18 source columns
-- - daily grain
-- - no session-level identifier in current export
-- - percentage values are preserved as source TEXT
--
-- Raw-layer principle:
-- Preserve source truth. Cleaning, NULL normalization,
-- percentage conversion, numeric conversion, and business
-- logic belong downstream in dbt staging.
-- ============================================================


CREATE TABLE IF NOT EXISTS raw.live_daily (

    -- --------------------------------------------------------
    -- Internal raw-row identity
    -- --------------------------------------------------------

    raw_live_daily_row_id
        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,


    -- --------------------------------------------------------
    -- Source columns: 1-10
    -- --------------------------------------------------------

    metric_date TEXT NOT NULL,
    live_attributed_gmv TEXT,
    live_direct_gmv TEXT,
    live_indirect_gmv TEXT,
    display_gpm TEXT,
    live_stream_count TEXT,
    gmv_generating_live_stream_count TEXT,
    live_attributed_items_sold TEXT,
    live_direct_items_sold TEXT,
    live_indirect_items_sold TEXT,


    -- --------------------------------------------------------
    -- Source columns: 11-18
    -- --------------------------------------------------------

    attributed_sku_orders TEXT,
    live_direct_sku_orders TEXT,
    live_indirect_sku_orders TEXT,
    customers_search TEXT,
    live_click_through_rate TEXT,
    live_sku_order_ctor TEXT,
    live_views TEXT,
    average_live_watch_duration TEXT,


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

    CONSTRAINT fk_raw_live_daily_pipeline_run
        FOREIGN KEY (_pipeline_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_raw_live_daily_ingestion_file
        FOREIGN KEY (_ingestion_file_id)
        REFERENCES audit.ingestion_files (ingestion_file_id)
        ON DELETE RESTRICT,


    -- --------------------------------------------------------
    -- Raw-row identity inside one source file
    -- --------------------------------------------------------

    CONSTRAINT uq_raw_live_daily_file_source_row
        UNIQUE (
            _ingestion_file_id,
            _source_row_number
        ),


    -- --------------------------------------------------------
    -- Metadata validation
    -- --------------------------------------------------------

    CONSTRAINT chk_raw_live_daily_source_row_number
        CHECK (_source_row_number > 0),

    CONSTRAINT chk_raw_live_daily_file_hash_length
        CHECK (char_length(_file_hash) = 64)
);


-- ============================================================
-- Operational / lineage indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_raw_live_daily_metric_date
    ON raw.live_daily (metric_date);

CREATE INDEX IF NOT EXISTS idx_raw_live_daily_pipeline_run_id
    ON raw.live_daily (_pipeline_run_id);

CREATE INDEX IF NOT EXISTS idx_raw_live_daily_ingestion_file_id
    ON raw.live_daily (_ingestion_file_id);

CREATE INDEX IF NOT EXISTS idx_raw_live_daily_file_hash
    ON raw.live_daily (_file_hash);

CREATE INDEX IF NOT EXISTS idx_raw_live_daily_ingested_at
    ON raw.live_daily (_ingested_at DESC);


COMMIT;