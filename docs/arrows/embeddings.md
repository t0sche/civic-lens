# Arrow: embeddings

Section-aware document chunking, embedding generation, and pgvector storage for RAG retrieval.

## Status

**MAPPED** - 2026-03-14. Chunking strategy outlined in HLD D4; implementation not yet started.

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

None yet — UNMAPPED.

## Work Required

### Must Fix
1. Section-aware chunker for eCode360 HTML (chapter → section → subsection boundaries)
2. Chunker for legislative text (bill articles, sections)
3. Embedding generation pipeline (run during ingestion, not at query time)
4. pgvector similarity search with metadata filtering (jurisdiction, source_type)

### Should Fix
1. Sub-chunking strategy for oversized sections (>2000 tokens) with overlap
2. Hierarchical breadcrumb preservation ("Town Code > Ch. 165 > §165-23 > (b)(3)")
3. Embedding model comparison (MiniLM vs. Gemini vs. legal-domain model)

### Nice to Have
1. Hybrid search (vector similarity + full-text keyword search via Postgres tsvector)
2. Re-embedding triggered by Silver layer changes (not full re-index)
