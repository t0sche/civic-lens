# Arrow: embeddings

Section-aware document chunking, embedding generation, and pgvector storage for RAG retrieval.

## Status

**PARTIALLY_IMPLEMENTED** - 2026-03-19. chunker.py, embedder.py, and vector_search.py are all implemented. EMBED-GEN-002 (MiniLM local model) is deferred — raises ValueError for "minilm" rather than using sentence-transformers.

## References

### HLD
- docs/high-level-design.md §4.2 (Embeddings row), §5 D4 (section-aware chunking), §7 Gold layer schema

### LLD
- docs/llds/embeddings.md (created 2026-03-14)

### EARS
- docs/specs/embeddings-specs.md (21 specs: 18 active, 3 deferred)

### Tests
- tests/pipeline/test_chunking.py
- tests/pipeline/test_embeddings.py

### Code
- src/pipeline/chunker.py — section-aware document chunking (IMPLEMENTED)
- src/pipeline/embedder.py — embedding generation and pgvector upsert (IMPLEMENTED)
- src/lib/vector_search.py — pgvector similarity search with metadata filtering (IMPLEMENTED)

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

- chunker.py implements section-aware splitting for both eCode360 HTML and legislative text; breadcrumb metadata is preserved per chunk.
- embedder.py generates Gemini text-embedding-004 embeddings (768d) and upserts to document_chunks via pgvector.
- vector_search.py provides similarity search with jurisdiction/source_type metadata filtering for RAG retrieval.
- EMBED-GEN-002 (MiniLM local model) raises ValueError and is correctly deferred — sentence-transformers dependency not installed.

## Work Required

### Should Fix
1. Retrieval quality evaluation: build a 20-question test set and measure recall@8 before Phase 9 launch.

### Nice to Have
1. Hybrid search (vector similarity + full-text keyword search via Postgres tsvector).
2. Re-embedding triggered by Silver layer changes (not full re-index).
3. Sub-chunking with overlap for sections exceeding 2000 tokens.
