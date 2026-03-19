# Arrow: embeddings

Section-aware document chunking, embedding generation, and pgvector storage for RAG retrieval.

## Status

**IMPLEMENTED** - 2026-03-19. chunker.py, embedder.py, and vector_search.py are fully built and integrated into CI.

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

As of 2026-03-19:
- **chunker.py** — section-aware chunker implemented; splits on legal section boundaries (not token count), preserves hierarchical breadcrumbs
- **embedder.py** — embedding generation pipeline using Gemini embedding API; MiniLM (EMBED-GEN-002) intentionally deferred; embedder raises ValueError on unsupported model
- **vector_search.py** — `match_document_chunks` RPC call with jurisdiction/type metadata filters
- EMBED-EVAL-001/002 (retrieval quality evaluation) deferred to Phase 9

## Work Required (Post-MVP)

### Phase 9
1. Retrieval quality evaluation — 20-question test set, recall@8 metric
2. Sub-chunking for oversized sections (>2000 tokens) with overlap
3. Hybrid search (pgvector + tsvector keyword fallback)
