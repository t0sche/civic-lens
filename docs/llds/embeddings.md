# Embeddings: Chunking and Vector Storage

**Created**: 2026-03-14
**Status**: Design Phase
**HLD Reference**: §4.2 Embeddings row, §5 D4 (section-aware chunking), §7 Gold layer

## Context and Design Philosophy

The embeddings pipeline transforms Silver layer documents into vector representations stored in pgvector for retrieval-augmented generation. The critical design decision is that chunks are split by **legal section boundaries**, not by token count. Legal text has natural semantic units — statute sections, code subsections, bill articles — and splitting mid-section destroys context that a resident's question depends on.

The tradeoff is uneven chunk sizes: some sections are 50 tokens (a short definition), others are 2,000 tokens (a detailed zoning regulation). The embedding model handles this variance, and retrieval quality is better with semantically coherent chunks than with uniform-length but context-broken ones.

## Chunking Strategy

### Code Sections (Primary MVP Content)

Code sections from eCode360 arrive in the Silver layer as individual `code_sections` records, each representing one numbered section of the municipal or county code. These are the natural chunk boundaries.

**Short sections** (≤4,000 characters): The entire section becomes a single chunk. The `section_path` breadcrumb (e.g., "Town of Bel Air Code > Chapter 165 > §165-23 Fences and walls") is stored as metadata for citation display.

**Long sections** (>4,000 characters): The section is sub-chunked at paragraph boundaries (`\n\n` splits). Each sub-chunk includes a 200-character overlap with the previous chunk to preserve context across chunk boundaries. The overlap ensures that a sentence split across two chunks can still be retrieved in either chunk's context window.

The 4,000-character threshold corresponds to roughly 800-1,000 tokens, which keeps each chunk well within the embedding model's effective range (most embedding models perform best on chunks of 256-512 tokens, but up to 1,000 is acceptable for legal text where context density is high).

### Legislative Items

Bills, ordinances, and resolutions in the Silver layer are typically represented by their title and summary. Full bill text (from LegiScan) is a future enhancement. For MVP:

- Each `legislative_item` produces a single chunk containing: `{title}\n\n{summary}`
- The `section_path` metadata is: `{body} > {title}` (e.g., "Maryland General Assembly > HB 100 - Property Tax Relief")

This is intentionally simple. Most resident questions about pending legislation are answerable from the title and summary. Full bill text chunking (with article/section boundary detection) is a Phase 4+ concern.

### Meeting Records (Phase 4)

Meeting minutes and agendas will require a different chunking approach since they don't have section numbers. The planned strategy (for later implementation):

1. Split by agenda item headers (typically numbered: "Item 1:", "New Business:", etc.)
2. Each agenda item becomes a chunk with metadata: `{body} > {meeting_date} > {item_title}`
3. Sub-chunk large items (lengthy discussion transcripts) at paragraph boundaries

## Embedding Model Selection

### Decision: Gemini text-embedding-004 (Default)

The Gemini embedding API is the default choice for three reasons:

1. **Free tier**: 1,500 requests/day, sufficient for the MVP corpus and incremental updates
2. **768-dimensional embeddings**: Good balance of quality and storage efficiency
3. **Task-type specialization**: Supports `RETRIEVAL_DOCUMENT` for indexing and `RETRIEVAL_QUERY` for search, improving retrieval quality

The embedding model is configurable via the `EMBEDDING_MODEL` environment variable ("gemini" or "minilm") to allow switching without code changes.

### Alternative: all-MiniLM-L6-v2

A local alternative that runs during the GitHub Action without API calls. Advantages: no API dependency, no rate limits, 384 dimensions (smaller storage). Disadvantage: lower quality on legal text compared to Gemini.

If the Gemini free tier becomes insufficient (corpus grows beyond 1,500 chunks needing embedding per day), switching to MiniLM eliminates the cost entirely at the expense of retrieval quality.

### Embedding Dimensions and Storage

At 768 dimensions (Gemini), each embedding is 768 × 4 bytes = 3,072 bytes (3KB). For an estimated 5,000 chunks at MVP scale, that's ~15MB of vector data — well within the 500MB Supabase free tier.

The `document_chunks` table uses `vector(768)`. If switching to MiniLM (384 dims), this requires a migration to change the column type and HNSW index configuration.

## pgvector Configuration

### Index Type: HNSW

HNSW (Hierarchical Navigable Small World) provides fast approximate nearest-neighbor search. The alternative, IVFFlat, requires periodic re-building after bulk inserts — HNSW doesn't, making it better suited to incremental ingestion.

**Index parameters:**
- `m = 16` — connections per node. Higher values improve recall at the cost of index size. 16 is the default and appropriate for a corpus under 100K vectors.
- `ef_construction = 64` — build-time search depth. Higher values produce better index quality at the cost of build time. 64 is sufficient for our corpus size.

**Query-time parameter:** `ef_search` (set via `SET hnsw.ef_search = 40` before querying) controls search quality vs. speed. Default of 40 is fine for interactive latency requirements.

### Similarity Metric: Cosine

The index uses `vector_cosine_ops` for cosine similarity. This is the standard choice for text embeddings where vector magnitude is not meaningful (all modern embedding models produce normalized vectors).

### Search Function

The `match_document_chunks` RPC function encapsulates the similarity search:

```sql
match_document_chunks(
  query_embedding vector(768),
  match_threshold float,      -- minimum similarity (0.0-1.0)
  match_count int,            -- max results
  filter_jurisdiction text    -- optional jurisdiction filter
)
```

The function returns chunks sorted by similarity (descending) with a configurable threshold. The threshold (default 0.3) filters out low-relevance noise — chunks below this similarity to the query are excluded even if fewer than `match_count` results are returned.

**Jurisdiction filtering** is applied as a SQL `WHERE` clause before the vector search, using the index's built-in support for combined filtering. This ensures that jurisdiction-scoped queries don't waste retrieval slots on irrelevant jurisdictions.

## Pipeline Execution

### Incremental Embedding

The embedding pipeline must avoid re-embedding unchanged content. The strategy:

1. For each Silver record, check if corresponding Gold chunks exist
2. If chunks exist and the Silver record's `updated_at` is older than the chunk's `created_at` → skip
3. If chunks don't exist or the Silver record is newer → delete existing chunks, re-chunk, re-embed

For MVP simplicity, the initial implementation can be delete-and-recreate (clear all chunks for a source_id, then regenerate). This is less efficient but simpler to reason about. Optimize to diff-based updates if embedding costs become a concern.

### Batch Processing

Embedding API calls should be batched where possible:
- Gemini supports single-text embedding per call (no batch endpoint in the free tier)
- Process chunks sequentially, one API call per chunk
- At ~500ms per Gemini call and ~5,000 chunks, a full re-embed takes ~40 minutes
- Incremental updates (10-50 new/changed chunks per run) take <30 seconds

If full re-embedding is needed (model change or dimension change), it can run as a one-time GitHub Actions workflow with a longer timeout.

## Retrieval Quality Considerations

### Legal Text Challenges

Legal text presents specific retrieval challenges that affect chunking and embedding quality:

**Cross-references**: "As defined in §4-201(b)(3)" — the referenced section contains the actual definition, but the embedding of the referencing section won't capture it. Mitigation for post-MVP: build a reference graph and include referenced section text in the chunk's embedding context.

**Defined terms**: Legal codes define terms in one section and use them throughout. The embedding model may not connect a question about "setback requirements" to a section that uses the defined term "minimum yard depth." Mitigation: the enrichment pipeline could annotate chunks with their defined terms.

**Negative requirements**: "No fence shall exceed six feet" should match queries about maximum fence height, but embedding models sometimes struggle with negation. No specific mitigation — this is a known limitation of current embedding models, and retrieval threshold tuning helps surface relevant results.

### Evaluation Strategy

Retrieval quality should be evaluated with a small test set before launch:
1. Compile 20-30 representative resident questions (fence height, noise rules, home business permits, etc.)
2. For each question, manually identify the correct source sections
3. Run the RAG retrieval and measure recall@k (does the correct section appear in the top-k results?)
4. Target: >80% recall@8 — if a question's answer exists in the corpus, it should appear in the top 8 retrieved chunks

This evaluation can be automated as a pytest fixture that runs after re-embedding.

## Open Questions & Future Decisions

### Resolved
1. ✅ Section-aware over token-count chunking — preserves legal text semantics
2. ✅ Gemini embedding as default — free, good quality, task-type specialization
3. ✅ HNSW over IVFFlat — no rebuild needed after incremental inserts
4. ✅ Cosine similarity — standard for normalized text embeddings

### Deferred
1. Hybrid search (vector + full-text keyword via tsvector) — useful for exact term matching ("§165-23"), defer until retrieval evaluation reveals gaps
2. Cross-reference expansion in chunk context — needed for "as defined in" resolution
3. Legal-domain embedding model evaluation — worth testing if retrieval quality is insufficient with Gemini
4. Re-embedding trigger on Silver changes — MVP does full scan; optimize later

## References

- pgvector HNSW: https://github.com/pgvector/pgvector#hnsw
- Gemini embedding API: https://ai.google.dev/gemini-api/docs/embeddings
- all-MiniLM-L6-v2: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
