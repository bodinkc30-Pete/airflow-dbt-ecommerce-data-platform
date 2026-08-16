BEGIN;

-- ============================================================
-- Project 06
-- Raw Product Master Physical Model
--
-- Source:
-- TikTok Product Master Excel export
--
-- Observed source characteristics:
-- - 1 row = 1 product snapshot record
-- - product_id is present and stable in the current export
-- - 176 source columns
-- - two-level Excel header structure
-- - repeated metric names across channel groups
--
-- Raw representation:
-- Important identity/lifecycle attributes are explicit columns.
-- The complete source record is preserved in source_payload JSONB
-- using canonical two-level header keys.
--
-- Example canonical payload keys:
--   ทั้งหมด::GMV
--   LIVE ของผู้ขาย::CTR
--   วิดีโอของผู้ขาย::GMV
--   แอฟฟิลิเอต::GMV
--   การ์ดสินค้าของผู้ขาย::CTR
--
-- Raw-layer principle:
-- Preserve source truth. Numeric conversion, currency parsing,
-- percentage conversion, lifecycle standardization, metric
-- interpretation, and analytical flattening belong downstream.
-- ============================================================


CREATE TABLE IF NOT EXISTS raw.products (

    -- --------------------------------------------------------
    -- Internal raw-row identity
    -- --------------------------------------------------------

    raw_product_row_id
        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,


    -- --------------------------------------------------------
    -- Core source identity / lifecycle attributes
    -- --------------------------------------------------------

    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    gmv_tier TEXT,
    product_status TEXT,


    -- --------------------------------------------------------
    -- Complete canonicalized source record
    -- --------------------------------------------------------

    source_payload JSONB NOT NULL,

    header_schema_version TEXT NOT NULL
        DEFAULT 'product_master_header_v1',


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

    CONSTRAINT fk_raw_products_pipeline_run
        FOREIGN KEY (_pipeline_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_raw_products_ingestion_file
        FOREIGN KEY (_ingestion_file_id)
        REFERENCES audit.ingestion_files (ingestion_file_id)
        ON DELETE RESTRICT,


    -- --------------------------------------------------------
    -- Raw-row identity inside one source file
    -- --------------------------------------------------------

    CONSTRAINT uq_raw_products_file_source_row
        UNIQUE (
            _ingestion_file_id,
            _source_row_number
        ),


    -- --------------------------------------------------------
    -- Raw metadata / identity validation
    -- --------------------------------------------------------

    CONSTRAINT chk_raw_products_product_id_not_blank
        CHECK (btrim(product_id) <> ''),

    CONSTRAINT chk_raw_products_product_name_not_blank
        CHECK (btrim(product_name) <> ''),

    CONSTRAINT chk_raw_products_source_payload_object
        CHECK (jsonb_typeof(source_payload) = 'object'),

    CONSTRAINT chk_raw_products_source_row_number
        CHECK (_source_row_number > 0),

    CONSTRAINT chk_raw_products_file_hash_length
        CHECK (char_length(_file_hash) = 64),

    CONSTRAINT chk_raw_products_header_schema_version_not_blank
        CHECK (btrim(header_schema_version) <> '')
);


-- ============================================================
-- Business / operational / lineage indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_raw_products_product_id
    ON raw.products (product_id);

CREATE INDEX IF NOT EXISTS idx_raw_products_product_status
    ON raw.products (product_status);

CREATE INDEX IF NOT EXISTS idx_raw_products_pipeline_run_id
    ON raw.products (_pipeline_run_id);

CREATE INDEX IF NOT EXISTS idx_raw_products_ingestion_file_id
    ON raw.products (_ingestion_file_id);

CREATE INDEX IF NOT EXISTS idx_raw_products_file_hash
    ON raw.products (_file_hash);

CREATE INDEX IF NOT EXISTS idx_raw_products_ingested_at
    ON raw.products (_ingested_at DESC);

CREATE INDEX IF NOT EXISTS idx_raw_products_source_payload_gin
    ON raw.products
    USING GIN (source_payload);


COMMIT;