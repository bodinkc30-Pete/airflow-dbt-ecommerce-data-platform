BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ecommerce_ingest_writer') THEN
        CREATE ROLE ecommerce_ingest_writer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ecommerce_transformer') THEN
        CREATE ROLE ecommerce_transformer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ecommerce_analytics_reader') THEN
        CREATE ROLE ecommerce_analytics_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
END
$$;

GRANT ecommerce_ingest_writer TO airflow;
GRANT ecommerce_transformer TO airflow;
GRANT ecommerce_analytics_reader TO airflow;

REVOKE ALL ON DATABASE ecommerce FROM PUBLIC;
GRANT CONNECT ON DATABASE ecommerce TO ecommerce_ingest_writer, ecommerce_transformer, ecommerce_analytics_reader;
GRANT TEMPORARY ON DATABASE ecommerce TO ecommerce_transformer;

REVOKE ALL ON SCHEMA raw, audit, analytics_staging, analytics_identity,
    analytics_intermediate, analytics_marts FROM PUBLIC;

GRANT USAGE ON SCHEMA raw, audit TO ecommerce_ingest_writer;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA raw, audit TO ecommerce_ingest_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA raw, audit TO ecommerce_ingest_writer;

ALTER DEFAULT PRIVILEGES FOR ROLE airflow IN SCHEMA raw
    GRANT SELECT, INSERT, UPDATE ON TABLES TO ecommerce_ingest_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE airflow IN SCHEMA audit
    GRANT SELECT, INSERT, UPDATE ON TABLES TO ecommerce_ingest_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE airflow IN SCHEMA raw
    GRANT USAGE, SELECT ON SEQUENCES TO ecommerce_ingest_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE airflow IN SCHEMA audit
    GRANT USAGE, SELECT ON SEQUENCES TO ecommerce_ingest_writer;

GRANT USAGE ON SCHEMA raw TO ecommerce_transformer;
GRANT SELECT ON raw.campaign_daily, raw.influencer_roster, raw.live_daily,
    raw.product_card_daily, raw.products, raw.shop_daily, raw.skus
TO ecommerce_transformer;

GRANT SELECT (
    raw_order_row_id, order_id, order_status, order_substatus,
    cancelation_return_type, normal_or_pre_order, sku_id, seller_sku,
    product_name, variation, quantity, sku_quantity_of_return,
    sku_unit_original_price, sku_subtotal_before_discount,
    sku_platform_discount, sku_seller_discount, sku_subtotal_after_discount,
    shipping_fee_after_discount, original_shipping_fee,
    shipping_fee_seller_discount, shipping_fee_platform_discount,
    payment_platform_discount, taxes, order_amount, order_refund_amount,
    created_time, paid_time, rts_time, shipped_time, delivered_time,
    cancelled_time, cancel_by, cancel_reason, fulfillment_type,
    warehouse_name, delivery_option, shipping_provider_name, payment_method,
    weight_kg, product_category, checked_status, order_channel,
    creator_handle, request_tax_invoice,
    _source_file, _source_row_number, _batch_id, _file_hash,
    _ingested_at, _pipeline_run_id, _ingestion_file_id
) ON raw.orders TO ecommerce_transformer;

ALTER SCHEMA analytics_staging OWNER TO ecommerce_transformer;
ALTER SCHEMA analytics_identity OWNER TO ecommerce_transformer;
ALTER SCHEMA analytics_intermediate OWNER TO ecommerce_transformer;
ALTER SCHEMA analytics_marts OWNER TO ecommerce_transformer;

DO $$
DECLARE
    relation RECORD;
    ddl TEXT;
BEGIN
    FOR relation IN
        SELECT n.nspname, c.relname, c.relkind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN (
            'analytics_staging', 'analytics_identity',
            'analytics_intermediate', 'analytics_marts'
        )
          AND c.relkind IN ('r', 'p', 'v', 'm', 'S')
    LOOP
        ddl := CASE relation.relkind
            WHEN 'v' THEN format('ALTER VIEW %I.%I OWNER TO ecommerce_transformer', relation.nspname, relation.relname)
            WHEN 'm' THEN format('ALTER MATERIALIZED VIEW %I.%I OWNER TO ecommerce_transformer', relation.nspname, relation.relname)
            WHEN 'S' THEN format('ALTER SEQUENCE %I.%I OWNER TO ecommerce_transformer', relation.nspname, relation.relname)
            ELSE format('ALTER TABLE %I.%I OWNER TO ecommerce_transformer', relation.nspname, relation.relname)
        END;
        EXECUTE ddl;
    END LOOP;
END
$$;

GRANT USAGE ON SCHEMA analytics_marts TO ecommerce_analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics_marts TO ecommerce_analytics_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE ecommerce_transformer IN SCHEMA analytics_marts
    GRANT SELECT ON TABLES TO ecommerce_analytics_reader;

CREATE TABLE IF NOT EXISTS audit.data_retention_policies (
    policy_key TEXT PRIMARY KEY,
    data_domain TEXT NOT NULL,
    policy_status TEXT NOT NULL DEFAULT 'pending_business_approval',
    retention_days INTEGER,
    enforcement_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    rationale TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_retention_policy_status
        CHECK (policy_status IN ('pending_business_approval', 'approved')),
    CONSTRAINT chk_retention_days_positive
        CHECK (retention_days IS NULL OR retention_days > 0),
    CONSTRAINT chk_retention_enforcement_approval
        CHECK (
            enforcement_enabled = FALSE
            OR (policy_status = 'approved' AND retention_days IS NOT NULL)
        )
);

INSERT INTO audit.data_retention_policies (
    policy_key, data_domain, retention_days, enforcement_enabled, rationale
)
VALUES
    (
        'raw_restricted_business_data', 'raw', NULL, FALSE,
        'Private business data may include PII; retention requires business/legal approval.'
    ),
    (
        'audit_lineage', 'audit', NULL, FALSE,
        'Audit run/file lineage must not be purged while raw foreign-key references remain.'
    ),
    (
        'pipeline_monitoring', 'audit', NULL, FALSE,
        'Monitoring retention is review-only until an operational SLA is approved.'
    ),
    (
        'resolved_incidents', 'audit', NULL, FALSE,
        'Incident evidence is retained until an approved operational retention policy exists.'
    )
ON CONFLICT (policy_key) DO NOTHING;

COMMENT ON TABLE audit.data_retention_policies IS
    'Non-destructive retention policy registry. Enforcement stays disabled until business/legal approval.';

COMMIT;
