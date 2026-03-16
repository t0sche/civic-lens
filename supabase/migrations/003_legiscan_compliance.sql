-- CivicLens: LegiScan API compliance — hash tracking and attribution
-- Migration: 003_legiscan_compliance
-- Date: 2026-03-16
--
-- Adds LegiScan-specific columns to support API compliance:
-- 1. legiscan_change_hash: 32-char hash from LegiScan for bill change detection
-- 2. legiscan_dataset_hash: 32-char hash from LegiScan for dataset change detection
-- 3. data_source_attribution: Human-readable attribution string (CC BY 4.0)

-- Add LegiScan change_hash to bronze_documents for hash-based dedup
alter table bronze_documents
    add column if not exists legiscan_change_hash text;

comment on column bronze_documents.legiscan_change_hash is
    'LegiScan change_hash (32 chars) for bill change detection. '
    'Compare before fetching to avoid unnecessary API queries.';

-- Index for fast hash lookups when comparing against master list
create index if not exists idx_bronze_legiscan_hash
    on bronze_documents(legiscan_change_hash)
    where source = 'legiscan';

-- Track dataset hashes per session for bulk download dedup
create table if not exists legiscan_dataset_hashes (
    session_id integer primary key,
    dataset_hash text not null,        -- 32-char hash from getDatasetList
    dataset_id integer,                -- LegiScan dataset ID
    checked_at timestamptz not null default now(),
    downloaded_at timestamptz          -- null if hash matched and download was skipped
);

comment on table legiscan_dataset_hashes is
    'Tracks LegiScan dataset_hash per session to prevent duplicative '
    'downloads. Per API terms: failure to use dataset_hash will result '
    'in suspended access.';

-- Add source attribution to document_chunks metadata convention.
-- This is informational — the actual attribution is stored in
-- document_chunks.metadata->>'source' during the embedding pipeline.
comment on column document_chunks.metadata is
    'Flexible metadata for retrieval filtering. '
    'For LegiScan-sourced chunks, includes "source": "legiscan" '
    'for CC BY 4.0 attribution in the UI.';
