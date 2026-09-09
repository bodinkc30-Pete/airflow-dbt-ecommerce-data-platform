BEGIN;

ALTER TABLE audit.pipeline_alerts
    ADD COLUMN IF NOT EXISTS root_cause_category TEXT,
    ADD COLUMN IF NOT EXISTS root_cause_summary TEXT,
    ADD COLUMN IF NOT EXISTS remediation_summary TEXT,
    ADD COLUMN IF NOT EXISTS recovery_dag_run_id TEXT,
    ADD COLUMN IF NOT EXISTS verification_summary TEXT,
    ADD COLUMN IF NOT EXISTS resolution_details JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_pipeline_alert_root_cause_category'
          AND conrelid = 'audit.pipeline_alerts'::regclass
    ) THEN
        ALTER TABLE audit.pipeline_alerts
            ADD CONSTRAINT chk_pipeline_alert_root_cause_category
            CHECK (
                root_cause_category IS NULL
                OR root_cause_category IN (
                    'transient_dependency', 'database', 'data_quality',
                    'schema', 'transformation', 'orchestration',
                    'timeout', 'resource', 'configuration', 'unknown'
                )
            );
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_pipeline_alert_resolution_contract'
          AND conrelid = 'audit.pipeline_alerts'::regclass
    ) THEN
        ALTER TABLE audit.pipeline_alerts
            ADD CONSTRAINT chk_pipeline_alert_resolution_contract
            CHECK (
                (
                    resolved = FALSE
                    AND resolved_at IS NULL
                )
                OR (
                    resolved = TRUE
                    AND resolved_at IS NOT NULL
                    AND root_cause_category IS NOT NULL
                    AND NULLIF(BTRIM(root_cause_summary), '') IS NOT NULL
                    AND NULLIF(BTRIM(remediation_summary), '') IS NOT NULL
                    AND NULLIF(BTRIM(recovery_dag_run_id), '') IS NOT NULL
                    AND NULLIF(BTRIM(verification_summary), '') IS NOT NULL
                )
            );
    END IF;
END
$$;

COMMIT;
