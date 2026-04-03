# Arrow: embeddings

Section-aware document chunking, embedding generation, and pgvector storage for RAG retrieval.

## Status

**IMPLEMENTED** - 2026-03-19. Section-aware chunker, embedding generation pipeline, and pgvector retrieval all shipped in Phases 5–7.

## References

### HLD
- docs/high-level-design.md §4.2 (Embeddings row), §5 D4 (section-aware chunking), §7 Gold layer schema

### LLD
- docs/llds/embeddings.md (created 2026-03-14)

### EARS
- docs/specs/embeddings-specs.md (21 specs: 19 active, 2 deferred)

### Tests
- tests/pipeline/test_chunking.py
- tests/pipeline/test_embeddings.py

### Code
- src/pipeline/chunker.py — section-aware document chunking
- src/pipeline/embedder.py — embedding generation and pgvector upsert
- src/lib/vector_search.py — pgvector similarity search with metadata filtering

## Architecture

**Purpose:** Transform Silver layer documents into retrievable vector embeddings. The chunking strategy must preserve legal text semantics — statute sections, code subsections, and bill articles are natural boundaries.

**Key Components:**
1. Section-aware chunker — splits by legal section boundaries, not token count; preserves hierarchical breadcrumbs
2. Embedding generator — converts chunks to vectors using Gemini embedding API or all-MiniLM-L6-v2
3. pgvector storage — document_chunk table with metadata for filtered retrieval
4. Retrieval interface — similarity search with jurisdiction/type/date filters for RAG pipeline

## EARS Coverage

See spec file in References above.

## Key Findings

- `src/pipeline/chunker.py` — section-aware chunker using BeautifulSoup to split eCode360 HTML at chapter/section/subsection boundaries; preserves breadcrumb hierarchy in metadata
- `src/pipeline/embedder.py` — generates embeddings via Gemini `text-embedding-004` with `RETRIEVAL_DOCUMENT` task type; upserts vectors to `document_chunks` via Supabase RPC; raises `ValueError` for unsupported model names (MiniLM intentionally deferred per EMBED-GEN-002)
- `src/lib/vector_search.py` — calls `match_document_chunks` Postgres RPC; supports jurisdiction and source_type filters; returns top-k chunks with similarity scores
- All 19 active specs (EMBED-CHUNK through EMBED-SEARCH) verified implemented; EMBED-GEN-002 (MiniLM) and EMBED-EVAL-001/002 deferred to Phase 9

## Work Required

### Phase 9
1. Retrieval quality evaluation: 20-question test set, recall@8 metric (EMBED-EVAL-001/002)
2. MiniLM fallback embedding model (EMBED-GEN-002)
3. Hybrid search (vector + tsvector full-text, EMBED-SEARCH-003 deferred)
