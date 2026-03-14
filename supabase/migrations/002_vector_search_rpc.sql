-- CivicLens: pgvector similarity search function
-- Migration: 002_vector_search_rpc
-- Date: 2026-03-14
--
-- Called by the RAG pipeline to find document chunks similar to a query embedding.
-- Supports optional jurisdiction filtering for scoped queries.

create or replace function match_document_chunks(
    query_embedding vector(768),
    match_threshold float default 0.3,
    match_count int default 8,
    filter_jurisdiction text default null
)
returns table (
    id uuid,
    chunk_text text,
    section_path text,
    jurisdiction jurisdiction_level,
    source_type chunk_source_type,
    source_id uuid,
    metadata jsonb,
    similarity float
)
language plpgsql
as $$
begin
    return query
    select
        dc.id,
        dc.chunk_text,
        dc.section_path,
        dc.jurisdiction,
        dc.source_type,
        dc.source_id,
        dc.metadata,
        1 - (dc.embedding <=> query_embedding) as similarity
    from document_chunks dc
    where
        1 - (dc.embedding <=> query_embedding) > match_threshold
        and (filter_jurisdiction is null or dc.jurisdiction::text = filter_jurisdiction)
    order by dc.embedding <=> query_embedding
    limit match_count;
end;
$$;
