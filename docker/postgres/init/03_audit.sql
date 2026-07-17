-- =========================================================
-- 03_audit.sql - batch tracking for ingestion runs
-- Records every Bronze ingestion for full lineage (DPRD requirement)
-- =========================================================

\connect retail_dwh

CREATE SCHEMA IF NOT EXISTS audit AUTHORIZATION retail_owner;
GRANT USAGE ON SCHEMA audit TO retail_readonly;

CREATE TABLE IF NOT EXISTS audit.ingestion_batches (
    batch_id           TEXT PRIMARY KEY,
    source_name        TEXT NOT NULL,
    source_uri         TEXT NOT NULL,
    file_name          TEXT NOT NULL,
    file_sha256        TEXT NOT NULL,
    file_size_bytes    BIGINT NOT NULL,
    row_count          BIGINT,
    ingest_started_at  TIMESTAMPTZ NOT NULL,
    ingest_finished_at TIMESTAMPTZ,
    status             TEXT NOT NULL CHECK (status IN ('running','success','failed')),
    error_message      TEXT,
    bronze_path        TEXT
);

ALTER TABLE audit.ingestion_batches OWNER TO retail_owner;
GRANT SELECT ON audit.ingestion_batches TO retail_readonly;

CREATE INDEX IF NOT EXISTS ix_batches_source_started
    ON audit.ingestion_batches (source_name, ingest_started_at DESC);
