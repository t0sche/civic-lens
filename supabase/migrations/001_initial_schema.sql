-- CivicLens: Initial schema — Bronze / Silver / Gold medallion architecture
-- Migration: 001_initial_schema
-- Date: 2026-03-14

-- Enable pgvector extension for embedding storage
create extension if not exists vector;

-- ═══════════════════════════════════════════════════════════════════════
-- BRONZE LAYER — Raw ingested data, source-faithful
-- ═══════════════════════════════════════════════════════════════════════

create table bronze_documents (
    id              uuid primary key default gen_random_uuid(),
    source          text not null,          -- 'openstates', 'legiscan', 'ecode360_belair', 'civicplus_belair', etc.
    source_id       text,                   -- Original ID from source system
    document_type   text not null,          -- 'bill', 'code_section', 'agenda', 'minutes', 'ordinance', etc.
    raw_content     text not null,          -- Full raw text or HTML
    raw_metadata    jsonb default '{}',     -- Source-specific metadata preserved as-is
    url             text,                   -- Source URL
    fetched_at      timestamptz not null default now(),
    content_hash    text,                   -- SHA-256 of raw_content for change detection
    
    unique(source, source_id)
);

create index idx_bronze_source on bronze_documents(source);
create index idx_bronze_type on bronze_documents(document_type);
create index idx_bronze_fetched on bronze_documents(fetched_at desc);

-- ═══════════════════════════════════════════════════════════════════════
-- SILVER LAYER — Normalized, enriched, queryable
-- ═══════════════════════════════════════════════════════════════════════

-- Jurisdiction enum
create type jurisdiction_level as enum ('STATE', 'COUNTY', 'MUNICIPAL');

-- Legislative item status enum
create type legislative_status as enum (
    'INTRODUCED', 'IN_COMMITTEE', 'PASSED_ONE_CHAMBER', 'ENACTED',
    'VETOED', 'EXPIRED', 'PENDING', 'TABLED', 'REJECTED', 'APPROVED',
    'EFFECTIVE', 'UNKNOWN'
);

-- Legislative item type enum
create type legislative_type as enum (
    'BILL', 'ORDINANCE', 'RESOLUTION', 'EXECUTIVE_ORDER',
    'ZONING_CHANGE', 'POLICY', 'AGENDA_ITEM', 'OTHER'
);

-- Unified legislative item (bills, ordinances, resolutions, etc.)
create table legislative_items (
    id                  uuid primary key default gen_random_uuid(),
    bronze_id           uuid references bronze_documents(id),
    source_id           text not null,          -- Bill number, ordinance number, etc.
    jurisdiction        jurisdiction_level not null,
    body                text not null,          -- "Maryland General Assembly", "Harford County Council", etc.
    item_type           legislative_type not null,
    title               text not null,
    summary             text,                   -- LLM-generated plain-language summary
    status              legislative_status not null default 'UNKNOWN',
    introduced_date     date,
    last_action_date    date,
    last_action         text,                   -- Human-readable last action
    sponsors            text[] default '{}',
    source_url          text,
    tags                text[] default '{}',    -- LLM-generated topic tags
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create index idx_legitem_jurisdiction on legislative_items(jurisdiction);
create index idx_legitem_status on legislative_items(status);
create index idx_legitem_type on legislative_items(item_type);
create index idx_legitem_lastaction on legislative_items(last_action_date desc);
create index idx_legitem_tags on legislative_items using gin(tags);

-- Codified law sections (county code, town code)
create table code_sections (
    id                  uuid primary key default gen_random_uuid(),
    bronze_id           uuid references bronze_documents(id),
    jurisdiction        jurisdiction_level not null,
    code_source         text not null,          -- "Harford County Code", "Town of Bel Air Code"
    chapter             text not null,          -- "Chapter 165 - Development Regulations"
    section             text not null,          -- "§165-23 Fences and walls"
    title               text not null,
    content             text not null,
    parent_section_id   uuid references code_sections(id),
    section_path        text,                   -- Hierarchical breadcrumb
    source_url          text,
    effective_date      date,
    last_amended        date,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create index idx_codesec_jurisdiction on code_sections(jurisdiction);
create index idx_codesec_source on code_sections(code_source);
create index idx_codesec_chapter on code_sections(chapter);

-- Meeting records (agendas, minutes)
create table meeting_records (
    id                  uuid primary key default gen_random_uuid(),
    bronze_id           uuid references bronze_documents(id),
    jurisdiction        jurisdiction_level not null,
    body                text not null,          -- "Board of Town Commissioners", "Planning Commission", etc.
    meeting_date        date not null,
    record_type         text not null,          -- 'agenda', 'minutes'
    title               text,
    content             text,                   -- Extracted text (may be null if PDF not yet processed)
    pdf_url             text,
    source_url          text,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

create index idx_meeting_jurisdiction on meeting_records(jurisdiction);
create index idx_meeting_body on meeting_records(body);
create index idx_meeting_date on meeting_records(meeting_date desc);

-- ═══════════════════════════════════════════════════════════════════════
-- GOLD LAYER — Embeddings for RAG retrieval
-- ═══════════════════════════════════════════════════════════════════════

create type chunk_source_type as enum (
    'LEGISLATIVE_ITEM', 'CODE_SECTION', 'MEETING_RECORD', 'OTHER'
);

create table document_chunks (
    id              uuid primary key default gen_random_uuid(),
    source_type     chunk_source_type not null,
    source_id       uuid not null,              -- FK to Silver layer record (legislative_items, code_sections, or meeting_records)
    jurisdiction    jurisdiction_level not null,
    chunk_text      text not null,
    chunk_index     integer not null default 0,  -- Position within source document
    section_path    text,                        -- Hierarchical breadcrumb for display
    embedding       vector(768),                 -- Gemini embedding dimensions (adjust if using MiniLM: 384)
    metadata        jsonb default '{}',          -- Flexible metadata for retrieval filtering
    created_at      timestamptz not null default now()
);

-- HNSW index for fast approximate nearest neighbor search
create index idx_chunks_embedding on document_chunks
    using hnsw (embedding vector_cosine_ops)
    with (m = 16, ef_construction = 64);

create index idx_chunks_source on document_chunks(source_type, source_id);
create index idx_chunks_jurisdiction on document_chunks(jurisdiction);

-- ═══════════════════════════════════════════════════════════════════════
-- OPERATIONAL — Ingestion tracking and freshness monitoring
-- ═══════════════════════════════════════════════════════════════════════

create table ingestion_runs (
    id              uuid primary key default gen_random_uuid(),
    source          text not null,              -- Same as bronze_documents.source
    started_at      timestamptz not null default now(),
    completed_at    timestamptz,
    status          text not null default 'running', -- 'running', 'success', 'failed'
    records_fetched integer default 0,
    records_new     integer default 0,
    records_updated integer default 0,
    error_message   text,
    metadata        jsonb default '{}'
);

create index idx_ingestion_source on ingestion_runs(source, started_at desc);

-- ═══════════════════════════════════════════════════════════════════════
-- FUNCTIONS — Auto-update timestamps
-- ═══════════════════════════════════════════════════════════════════════

create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger trg_legitem_updated before update on legislative_items
    for each row execute function update_updated_at();

create trigger trg_codesec_updated before update on code_sections
    for each row execute function update_updated_at();

create trigger trg_meeting_updated before update on meeting_records
    for each row execute function update_updated_at();
