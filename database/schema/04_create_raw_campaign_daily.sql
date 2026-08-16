BEGIN;

-- ============================================================
-- Project 06
-- Raw Campaign / Advertising Daily Physical Model
--
-- Source:
-- TikTok Campaign Overview Excel export
--
-- Observed source grain:
-- 1 row = 1 advertising-performance day
--
-- Important:
-- The current export does NOT contain campaign_id or
-- campaign_name. Therefore this raw model represents
-- shop-level daily advertising performance, not an
-- individual campaign-day grain.
--
-- Source summary row where reporting_date = '-'
-- must be identified before loading daily rows.
--
-- Raw-layer principle:
-- Preserve source truth. Source metric columns remain TEXT.
-- Type conversion and normalization belong downstream.
-- ============================================================


CREATE TABLE IF NOT EXISTS raw.campaign_daily (

    -- --------------------------------------------------------
    -- Internal raw-row identity
    -- --------------------------------------------------------

    raw_campaign_daily_row_id
        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,


    -- --------------------------------------------------------
    -- Source columns: 1-7
    -- --------------------------------------------------------

    metric_date TEXT NOT NULL,
    ad_cost TEXT,
    sku_orders TEXT,
    cost_per_order TEXT,
    gross_revenue TEXT,
    roi TEXT,
    currency TEXT,


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

    CONSTRAINT fk_raw_campaign_daily_pipeline_run
        FOREIGN KEY (_pipeline_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_raw_campaign_daily_ingestion_file
        FOREIGN KEY (_ingestion_file_id)
        REFERENCES audit.ingestion_files (ingestion_file_id)
        ON DELETE RESTRICT,


    -- --------------------------------------------------------
    -- Raw-row identity inside one source file
    -- --------------------------------------------------------

    CONSTRAINT uq_raw_campaign_daily_file_source_row
        UNIQUE (
            _ingestion_file_id,
            _source_row_number
        ),


    -- --------------------------------------------------------
    -- Metadata validation
    -- --------------------------------------------------------

    CONSTRAINT chk_raw_campaign_daily_source_row_number
        CHECK (_source_row_number > 0),

    CONSTRAINT chk_raw_campaign_daily_file_hash_length
        CHECK (char_length(_file_hash) = 64)
);


-- ============================================================
-- Operational / lineage indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_raw_campaign_daily_metric_date
    ON raw.campaign_daily (metric_date);

CREATE INDEX IF NOT EXISTS idx_raw_campaign_daily_pipeline_run_id
    ON raw.campaign_daily (_pipeline_run_id);

CREATE INDEX IF NOT EXISTS idx_raw_campaign_daily_ingestion_file_id
    ON raw.campaign_daily (_ingestion_file_id);

CREATE INDEX IF NOT EXISTS idx_raw_campaign_daily_file_hash
    ON raw.campaign_daily (_file_hash);

CREATE INDEX IF NOT EXISTS idx_raw_campaign_daily_ingested_at
    ON raw.campaign_daily (_ingested_at DESC);


COMMIT;