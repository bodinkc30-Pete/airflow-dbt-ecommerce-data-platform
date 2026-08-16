BEGIN;

-- ============================================================
-- Project 06
-- PostgreSQL Namespace + Ingestion Audit / Control Plane
-- ============================================================

-- ------------------------------------------------------------
-- 1. Namespaces
-- ------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS audit;


-- ------------------------------------------------------------
-- 2. Pipeline / ingestion run registry
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit.ingestion_runs (
    ingestion_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    pipeline_name TEXT NOT NULL,
    run_type TEXT NOT NULL DEFAULT 'scheduled',

    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,

    status TEXT NOT NULL DEFAULT 'running',

    files_discovered INTEGER NOT NULL DEFAULT 0,
    files_processed INTEGER NOT NULL DEFAULT 0,
    files_failed INTEGER NOT NULL DEFAULT 0,

    rows_discovered BIGINT NOT NULL DEFAULT 0,
    rows_loaded BIGINT NOT NULL DEFAULT 0,
    rows_rejected BIGINT NOT NULL DEFAULT 0,

    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_ingestion_runs_status
        CHECK (
            status IN (
                'running',
                'success',
                'failed',
                'partial_success',
                'cancelled'
            )
        ),

    CONSTRAINT chk_ingestion_runs_run_type
        CHECK (
            run_type IN (
                'scheduled',
                'manual',
                'backfill',
                'reprocessing',
                'test'
            )
        ),

    CONSTRAINT chk_ingestion_runs_finished_at
        CHECK (
            finished_at IS NULL
            OR finished_at >= started_at
        ),

    CONSTRAINT chk_ingestion_runs_file_counts
        CHECK (
            files_discovered >= 0
            AND files_processed >= 0
            AND files_failed >= 0
        ),

    CONSTRAINT chk_ingestion_runs_row_counts
        CHECK (
            rows_discovered >= 0
            AND rows_loaded >= 0
            AND rows_rejected >= 0
        )
);


-- ------------------------------------------------------------
-- 3. Source file registry
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit.ingestion_files (
    ingestion_file_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_run_id BIGINT NOT NULL,

    source_name TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,

    file_size_bytes BIGINT,
    file_modified_at TIMESTAMPTZ,

    file_hash_sha256 CHAR(64) NOT NULL,

    discovered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processing_started_at TIMESTAMPTZ,
    processing_finished_at TIMESTAMPTZ,

    status TEXT NOT NULL DEFAULT 'discovered',

    rows_discovered BIGINT NOT NULL DEFAULT 0,
    rows_loaded BIGINT NOT NULL DEFAULT 0,
    rows_rejected BIGINT NOT NULL DEFAULT 0,

    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_ingestion_files_run
        FOREIGN KEY (ingestion_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_ingestion_files_source_hash
        UNIQUE (source_name, file_hash_sha256),

    CONSTRAINT chk_ingestion_files_status
        CHECK (
            status IN (
                'discovered',
                'processing',
                'success',
                'failed',
                'skipped_duplicate',
                'rejected'
            )
        ),

    CONSTRAINT chk_ingestion_files_size
        CHECK (
            file_size_bytes IS NULL
            OR file_size_bytes >= 0
        ),

    CONSTRAINT chk_ingestion_files_row_counts
        CHECK (
            rows_discovered >= 0
            AND rows_loaded >= 0
            AND rows_rejected >= 0
        ),

    CONSTRAINT chk_ingestion_files_finished_at
        CHECK (
            processing_finished_at IS NULL
            OR processing_started_at IS NULL
            OR processing_finished_at >= processing_started_at
        )
);


-- ------------------------------------------------------------
-- 4. Persistent incremental state / watermarks
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit.source_watermarks (
    source_name TEXT PRIMARY KEY,

    watermark_type TEXT NOT NULL,

    watermark_value TEXT,

    last_successful_run_id BIGINT,
    last_successful_file_id BIGINT,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_source_watermarks_run
        FOREIGN KEY (last_successful_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_source_watermarks_file
        FOREIGN KEY (last_successful_file_id)
        REFERENCES audit.ingestion_files (ingestion_file_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_source_watermarks_type
        CHECK (
            watermark_type IN (
                'timestamp',
                'date',
                'integer',
                'string',
                'file'
            )
        )
);


-- ------------------------------------------------------------
-- 5. Schema drift / schema validation events
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit.schema_events (
    schema_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_run_id BIGINT,
    ingestion_file_id BIGINT,

    source_name TEXT NOT NULL,

    event_type TEXT NOT NULL,

    column_name TEXT,
    expected_value TEXT,
    observed_value TEXT,

    severity TEXT NOT NULL DEFAULT 'error',

    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,

    details JSONB,

    CONSTRAINT fk_schema_events_run
        FOREIGN KEY (ingestion_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_schema_events_file
        FOREIGN KEY (ingestion_file_id)
        REFERENCES audit.ingestion_files (ingestion_file_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_schema_events_type
        CHECK (
            event_type IN (
                'missing_column',
                'unexpected_column',
                'data_type_change',
                'column_order_change',
                'nullable_change',
                'schema_version_change',
                'other'
            )
        ),

    CONSTRAINT chk_schema_events_severity
        CHECK (
            severity IN (
                'info',
                'warning',
                'error',
                'critical'
            )
        ),

    CONSTRAINT chk_schema_events_resolved_at
        CHECK (
            resolved_at IS NULL
            OR resolved_at >= detected_at
        )
);


-- ------------------------------------------------------------
-- 6. Data-quality execution result registry
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit.data_quality_results (
    data_quality_result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_run_id BIGINT,
    ingestion_file_id BIGINT,

    source_name TEXT NOT NULL,

    check_name TEXT NOT NULL,
    check_category TEXT NOT NULL,

    status TEXT NOT NULL,

    rows_checked BIGINT,
    rows_failed BIGINT,

    expected_value TEXT,
    observed_value TEXT,

    failure_reason TEXT,

    checked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    details JSONB,

    CONSTRAINT fk_data_quality_results_run
        FOREIGN KEY (ingestion_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_data_quality_results_file
        FOREIGN KEY (ingestion_file_id)
        REFERENCES audit.ingestion_files (ingestion_file_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_data_quality_results_category
        CHECK (
            check_category IN (
                'file',
                'schema',
                'record',
                'identifier',
                'relationship',
                'business_rule',
                'reconciliation'
            )
        ),

    CONSTRAINT chk_data_quality_results_status
        CHECK (
            status IN (
                'pass',
                'fail',
                'warning',
                'skipped'
            )
        ),

    CONSTRAINT chk_data_quality_results_rows
        CHECK (
            (rows_checked IS NULL OR rows_checked >= 0)
            AND
            (rows_failed IS NULL OR rows_failed >= 0)
        )
);


-- ------------------------------------------------------------
-- 7. Operational indexes
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_pipeline_started_at
    ON audit.ingestion_runs (pipeline_name, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_status
    ON audit.ingestion_runs (status);

CREATE INDEX IF NOT EXISTS idx_ingestion_files_run_id
    ON audit.ingestion_files (ingestion_run_id);

CREATE INDEX IF NOT EXISTS idx_ingestion_files_source_status
    ON audit.ingestion_files (source_name, status);

CREATE INDEX IF NOT EXISTS idx_ingestion_files_hash
    ON audit.ingestion_files (file_hash_sha256);

CREATE INDEX IF NOT EXISTS idx_schema_events_source_detected_at
    ON audit.schema_events (source_name, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_schema_events_unresolved
    ON audit.schema_events (resolved, severity)
    WHERE resolved = FALSE;

CREATE INDEX IF NOT EXISTS idx_dq_results_run_id
    ON audit.data_quality_results (ingestion_run_id);

CREATE INDEX IF NOT EXISTS idx_dq_results_source_status
    ON audit.data_quality_results (source_name, status);

CREATE INDEX IF NOT EXISTS idx_dq_results_checked_at
    ON audit.data_quality_results (checked_at DESC);


COMMIT;