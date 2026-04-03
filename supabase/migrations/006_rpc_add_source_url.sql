-- CivicLens: add source_url to match_document_chunks RPC
-- Migration: 006_rpc_add_source_url
-- Date: 2026-03-19
--
-- Joins document_chunks with the Silver layer (legislative_items + code_sections)
-- to return the source URL alongside each chunk, enabling clickable citations in the UI.

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
    similarity float,
    source_url text
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
        1 - (dc.embedding <=> query_embedding) as similarity,
        coalesce(li.source_url, cs.source_url) as source_url
    from document_chunks dc
    left join legislative_items li
        on dc.source_type = 'LEGISLATIVE_ITEM' and dc.source_id = li.id
    left join code_sections cs
        on dc.source_type = 'CODE_SECTION' and dc.source_id = cs.id
    where
        1 - (dc.embedding <=> query_embedding) > match_threshold
        and (filter_jurisdiction is null or dc.jurisdiction::text = filter_jurisdiction)
    order by dc.embedding <=> query_embedding
    limit match_count;
end;
$$;
