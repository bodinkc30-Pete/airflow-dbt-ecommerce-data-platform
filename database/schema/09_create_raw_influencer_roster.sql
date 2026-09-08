BEGIN;

CREATE TABLE IF NOT EXISTS raw.influencer_roster (
    raw_influencer_row_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    influencer_name TEXT NOT NULL,
    follower_count TEXT,
    engagement_rate TEXT,
    budget TEXT,
    source_payload JSONB NOT NULL,
    header_schema_version TEXT NOT NULL DEFAULT 'influencer_roster_v1',
    _source_file TEXT NOT NULL,
    _source_row_number BIGINT NOT NULL,
    _batch_id TEXT NOT NULL,
    _file_hash CHAR(64) NOT NULL,
    _ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    _pipeline_run_id BIGINT NOT NULL,
    _ingestion_file_id BIGINT NOT NULL,
    CONSTRAINT fk_raw_influencer_roster_pipeline_run
        FOREIGN KEY (_pipeline_run_id)
        REFERENCES audit.ingestion_runs (ingestion_run_id) ON DELETE RESTRICT,
    CONSTRAINT fk_raw_influencer_roster_ingestion_file
        FOREIGN KEY (_ingestion_file_id)
        REFERENCES audit.ingestion_files (ingestion_file_id) ON DELETE RESTRICT,
    CONSTRAINT uq_raw_influencer_roster_file_source_row
        UNIQUE (_ingestion_file_id, _source_row_number),
    CONSTRAINT chk_raw_influencer_roster_name_not_blank
        CHECK (btrim(influencer_name) <> ''),
    CONSTRAINT chk_raw_influencer_roster_payload_object
        CHECK (jsonb_typeof(source_payload) = 'object'),
    CONSTRAINT chk_raw_influencer_roster_source_row_number
        CHECK (_source_row_number > 0),
    CONSTRAINT chk_raw_influencer_roster_file_hash_length
        CHECK (char_length(_file_hash) = 64),
    CONSTRAINT chk_raw_influencer_roster_schema_version_not_blank
        CHECK (btrim(header_schema_version) <> '')
);

CREATE INDEX IF NOT EXISTS idx_raw_influencer_roster_name
    ON raw.influencer_roster (influencer_name);
CREATE INDEX IF NOT EXISTS idx_raw_influencer_roster_pipeline_run_id
    ON raw.influencer_roster (_pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_raw_influencer_roster_ingestion_file_id
    ON raw.influencer_roster (_ingestion_file_id);
CREATE INDEX IF NOT EXISTS idx_raw_influencer_roster_file_hash
    ON raw.influencer_roster (_file_hash);
CREATE INDEX IF NOT EXISTS idx_raw_influencer_roster_payload_gin
    ON raw.influencer_roster USING GIN (source_payload);

COMMIT;
