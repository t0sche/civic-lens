-- Add unique constraint on document_chunks to prevent duplicate embeddings.
-- The embedder now uses upsert with this constraint instead of bare insert.
-- Migration: 007_document_chunks_unique
-- Date: 2026-04-02

-- Remove any existing duplicate chunks before adding the constraint.
-- Keep the most recent chunk (by created_at) for each (source_type, source_id, chunk_index).
delete from document_chunks a
using document_chunks b
where a.source_type = b.source_type
  and a.source_id = b.source_id
  and a.chunk_index = b.chunk_index
  and a.created_at < b.created_at;

alter table document_chunks
    add constraint uq_chunk_source
    unique (source_type, source_id, chunk_index);
