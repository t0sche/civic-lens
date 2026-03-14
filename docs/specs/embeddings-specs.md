# Embeddings Specifications

**Design Doc**: `/docs/llds/embeddings.md`
**Arrow**: `/docs/arrows/embeddings.md`

## Code Section Chunking

- [ ] **EMBED-CHUNK-001**: When a code section's content is 4,000 characters or fewer, the system shall produce exactly one chunk containing the full section text with metadata `full_section: true`.
- [ ] **EMBED-CHUNK-002**: When a code section's content exceeds 4,000 characters, the system shall split at paragraph boundaries (`\n\n`) into multiple sub-chunks, each 4,000 characters or fewer.
- [ ] **EMBED-CHUNK-003**: When sub-chunking a long section, the system shall include a 200-character overlap from the end of the previous chunk at the start of each subsequent chunk.
- [ ] **EMBED-CHUNK-004**: The system shall assign sequential chunk_index values (0, 1, 2, ...) to chunks produced from the same source document.
- [ ] **EMBED-CHUNK-005**: The system shall set source_type to CODE_SECTION and preserve the section_path from the Silver record on every chunk.
- [ ] **EMBED-CHUNK-006**: The system shall set the jurisdiction on every chunk to match the source Silver record's jurisdiction.

## Legislative Item Chunking

- [ ] **EMBED-CHUNK-010**: The system shall produce exactly one chunk per legislative_item containing the title and summary (if present) joined by a double newline.
- [ ] **EMBED-CHUNK-011**: When a legislative_item has no summary, the chunk shall contain only the title, and metadata shall include `has_summary: false`.
- [ ] **EMBED-CHUNK-012**: The system shall construct a section_path in the format "{body} > {title}" for each legislative_item chunk.

## Embedding Generation

- [ ] **EMBED-GEN-001**: When EMBEDDING_MODEL is set to "gemini", the system shall generate embeddings using the Gemini text-embedding-004 model with task_type "retrieval_document".
- [ ] **EMBED-GEN-002**: When EMBEDDING_MODEL is set to "minilm", the system shall generate embeddings using the local all-MiniLM-L6-v2 model via sentence-transformers.
- [ ] **EMBED-GEN-003**: If EMBEDDING_MODEL is set to an unrecognized value, then the system shall raise a ValueError identifying the invalid model name.
- [ ] **EMBED-GEN-004**: The system shall store generated embeddings in the document_chunks table's embedding column as vector(768) for Gemini or vector(384) for MiniLM.

## Gold Layer Writing

- [ ] **EMBED-WRITE-001**: The system shall write each chunk with its embedding, source_type, source_id, jurisdiction, chunk_text, chunk_index, section_path, and metadata to the document_chunks table.
- [ ] **EMBED-WRITE-002**: The system shall process all code_sections in the Silver layer when run without a source_type filter.
- [ ] **EMBED-WRITE-003**: The system shall process all legislative_items in the Silver layer when run without a source_type filter.

## Vector Search

- [ ] **EMBED-SEARCH-001**: The match_document_chunks function shall return chunks with cosine similarity above the specified threshold, ordered by descending similarity.
- [ ] **EMBED-SEARCH-002**: When a jurisdiction filter is provided, the match_document_chunks function shall return only chunks matching that jurisdiction.
- [ ] **EMBED-SEARCH-003**: The match_document_chunks function shall return at most match_count results.

## Retrieval Quality (Post-MVP Evaluation)

- [D] **EMBED-EVAL-001**: The system shall maintain a test set of at least 20 representative resident questions with manually identified correct source sections.
- [D] **EMBED-EVAL-002**: The system shall achieve at least 80% recall@8 on the test set — for questions whose answers exist in the corpus, the correct source section shall appear in the top 8 retrieved chunks.
