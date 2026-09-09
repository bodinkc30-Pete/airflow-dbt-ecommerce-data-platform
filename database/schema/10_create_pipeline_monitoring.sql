BEGIN;

-- ============================================================
-- Project 06
-- Pipeline Monitoring + Alert Outbox
-- ============================================================

CREATE TABLE IF NOT EXISTS audit.pipeline_monitoring_runs (
    monitoring_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    dag_id TEXT NOT NULL,
    dag_run_id TEXT NOT NULL,
    run_type TEXT NOT NULL,
    ingestion_run_id BIGINT,

    started_at TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    duration_seconds NUMERIC(14, 3) NOT NULL,

    status TEXT NOT NULL,
    is_slow BOOLEAN NOT NULL DEFAULT FALSE,
    slow_threshold_seconds INTEGER NOT NULL,

    files_discovered INTEGER NOT NULL DEFAULT 0,
    files_processed INTEGER NOT NULL DEFAULT 0,
    files_failed INTEGER NOT NULL DEFAULT 0,
    rows_discovered BIGINT NOT NULL DEFAULT 0,
    rows_loaded BIGINT NOT NULL DEFAULT 0,
    rows_rejected BIGINT NOT NULL DEFAULT 0,

    schema_error_count INTEGER NOT NULL DEFAULT 0,
    schema_warning_count INTEGER NOT NULL DEFAULT 0,
    ingestion_dq_fail_count INTEGER NOT NULL DEFAULT 0,
    ingestion_dq_warning_count INTEGER NOT NULL DEFAULT 0,

    dbt_freshness_warning_count INTEGER NOT NULL DEFAULT 0,
    dbt_blocking_error_count INTEGER NOT NULL DEFAULT 0,
    dbt_warning_count INTEGER NOT NULL DEFAULT 0,

    failed_task_count INTEGER NOT NULL DEFAULT 0,
    blocked_task_count INTEGER NOT NULL DEFAULT 0,

    task_states JSONB NOT NULL DEFAULT '{}'::jsonb,
    dbt_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT uq_pipeline_monitoring_dag_run UNIQUE (dag_id, dag_run_id),
    CONSTRAINT fk_pipeline_monitoring_ingestion_run
        FOREIGN KEY (ingestion_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE SET NULL,
    CONSTRAINT chk_pipeline_monitoring_status
        CHECK (status IN ('success', 'failed')),
    CONSTRAINT chk_pipeline_monitoring_duration
        CHECK (duration_seconds >= 0),
    CONSTRAINT chk_pipeline_monitoring_threshold
        CHECK (slow_threshold_seconds > 0),
    CONSTRAINT chk_pipeline_monitoring_counts
        CHECK (
            files_discovered >= 0
            AND files_processed >= 0
            AND files_failed >= 0
            AND rows_discovered >= 0
            AND rows_loaded >= 0
            AND rows_rejected >= 0
            AND schema_error_count >= 0
            AND schema_warning_count >= 0
            AND ingestion_dq_fail_count >= 0
            AND ingestion_dq_warning_count >= 0
            AND dbt_freshness_warning_count >= 0
            AND dbt_blocking_error_count >= 0
            AND dbt_warning_count >= 0
            AND failed_task_count >= 0
            AND blocked_task_count >= 0
        )
);

CREATE TABLE IF NOT EXISTS audit.pipeline_alerts (
    pipeline_alert_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    monitoring_run_id BIGINT NOT NULL,
    dag_id TEXT NOT NULL,
    dag_run_id TEXT NOT NULL,
    ingestion_run_id BIGINT,

    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,

    external_notification_requested BOOLEAN NOT NULL DEFAULT FALSE,
    delivery_status TEXT NOT NULL DEFAULT 'recorded',
    delivery_attempted_at TIMESTAMPTZ,
    delivery_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT uq_pipeline_alert_per_run_type
        UNIQUE (monitoring_run_id, alert_type),
    CONSTRAINT fk_pipeline_alert_monitoring_run
        FOREIGN KEY (monitoring_run_id)
        REFERENCES audit.pipeline_monitoring_runs (monitoring_run_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_pipeline_alert_ingestion_run
        FOREIGN KEY (ingestion_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id)
        ON DELETE SET NULL,
    CONSTRAINT chk_pipeline_alert_type
        CHECK (
            alert_type IN (
                'pipeline_failure',
                'slow_pipeline',
                'schema_drift',
                'data_quality_failure',
                'data_quality_warning',
                'dbt_freshness_warning',
                'dbt_warning'
            )
        ),
    CONSTRAINT chk_pipeline_alert_severity
        CHECK (severity IN ('warning', 'error', 'critical')),
    CONSTRAINT chk_pipeline_alert_delivery_status
        CHECK (
            delivery_status IN (
                'recorded',
                'not_configured',
                'sent',
                'failed'
            )
        ),
    CONSTRAINT chk_pipeline_alert_resolved_at
        CHECK (
            resolved_at IS NULL
            OR resolved_at >= created_at
        )
);

CREATE INDEX IF NOT EXISTS idx_pipeline_monitoring_observed_at
    ON audit.pipeline_monitoring_runs (observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_pipeline_monitoring_status
    ON audit.pipeline_monitoring_runs (status, is_slow, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_pipeline_alerts_open
    ON audit.pipeline_alerts (resolved, severity, created_at DESC)
    WHERE resolved = FALSE;

CREATE INDEX IF NOT EXISTS idx_pipeline_alerts_dag_run
    ON audit.pipeline_alerts (dag_id, dag_run_id);

CREATE OR REPLACE VIEW audit.pipeline_health_latest AS
SELECT DISTINCT ON (dag_id)
    dag_id,
    dag_run_id,
    run_type,
    status,
    is_slow,
    duration_seconds,
    rows_loaded,
    rows_rejected,
    schema_error_count,
    ingestion_dq_fail_count,
    dbt_freshness_warning_count,
    dbt_warning_count,
    failed_task_count,
    blocked_task_count,
    started_at,
    observed_at
FROM audit.pipeline_monitoring_runs
ORDER BY dag_id, observed_at DESC, monitoring_run_id DESC;

CREATE OR REPLACE VIEW audit.open_pipeline_alerts AS
SELECT
    pipeline_alert_id,
    dag_id,
    dag_run_id,
    alert_type,
    severity,
    message,
    delivery_status,
    created_at,
    delivery_attempted_at,
    delivery_error
FROM audit.pipeline_alerts
WHERE resolved = FALSE
ORDER BY created_at DESC, pipeline_alert_id DESC;

COMMIT;
