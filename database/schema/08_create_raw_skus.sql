BEGIN;

-- ============================================================
-- Project 06
-- Raw SKU Master Physical Model
--
-- Source:
-- TikTok SKU Master Excel export
--
-- Observed source grain:
-- 1 row = 1 SKU snapshot record
--
-- Business key:
-- sku_id
--
-- Relationship key:
-- product_id
--
-- Current source columns:
-- 1. SKU ID
-- 2. Product ID
-- 3. Product / SKU display name
-- 4. Status
-- 5. GMV
-- 6. SKU Orders
-- 7. Items Sold
--
-- Raw-layer principle:
-- Preserve source truth. Identifier trimming, lifecycle
-- standardization, numeric conversion, currency normalization,
-- reconciliation, and relationship validation belong
-- downstream in staging / data quality layers.
-- ============================================================


CREATE TABLE IF NOT EXISTS raw.skus (

    -- --------------------------------------------------------
    -- Internal raw-row identity
    -- --------------------------------------------------------

    raw_sku_row_id
        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,


    -- --------------------------------------------------------
    -- Source columns
    -- --------------------------------------------------------

    sku_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    sku_name TEXT NOT NULL,
    sku_status TEXT,
    gmv TEXT,
    sku_orders TEXT,
    items_sold TEXT,


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

    CONSTRAINT fk_raw_skus_pipeline_run
        FOREIGN KEY (_pipeline_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_raw_skus_ingestion_file
        FOREIGN KEY (_ingestion_file_id)
        REFERENCES audit.ingestion_files (ingestion_file_id)
        ON DELETE RESTRICT,


    -- --------------------------------------------------------
    -- Raw-row identity inside one source file
    -- --------------------------------------------------------

    CONSTRAINT uq_raw_skus_file_source_row
        UNIQUE (
            _ingestion_file_id,
            _source_row_number
        ),


    -- --------------------------------------------------------
    -- Raw identifier / metadata validation
    -- --------------------------------------------------------

    CONSTRAINT chk_raw_skus_sku_id_not_blank
        CHECK (btrim(sku_id) <> ''),

    CONSTRAINT chk_raw_skus_product_id_not_blank
        CHECK (btrim(product_id) <> ''),

    CONSTRAINT chk_raw_skus_sku_name_not_blank
        CHECK (btrim(sku_name) <> ''),

    CONSTRAINT chk_raw_skus_source_row_number
        CHECK (_source_row_number > 0),

    CONSTRAINT chk_raw_skus_file_hash_length
        CHECK (char_length(_file_hash) = 64)
);


-- ============================================================
-- Business / operational / lineage indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_raw_skus_sku_id
    ON raw.skus (sku_id);

CREATE INDEX IF NOT EXISTS idx_raw_skus_product_id
    ON raw.skus (product_id);

CREATE INDEX IF NOT EXISTS idx_raw_skus_sku_status
    ON raw.skus (sku_status);

CREATE INDEX IF NOT EXISTS idx_raw_skus_pipeline_run_id
    ON raw.skus (_pipeline_run_id);

CREATE INDEX IF NOT EXISTS idx_raw_skus_ingestion_file_id
    ON raw.skus (_ingestion_file_id);

CREATE INDEX IF NOT EXISTS idx_raw_skus_file_hash
    ON raw.skus (_file_hash);

CREATE INDEX IF NOT EXISTS idx_raw_skus_ingested_at
    ON raw.skus (_ingested_at DESC);


COMMIT;