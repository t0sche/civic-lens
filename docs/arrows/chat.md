# Arrow: chat

RAG-powered Q&A interface: query understanding, vector retrieval, model routing, prompt construction, citation generation, and legal disclaimers.

## Status

**MAPPED** - 2026-03-14. Architecture defined in HLD; no implementation yet.

## References

### HLD
- docs/high-level-design.md §4.1 (Chat Interface box), §4.2 (Chat model rows), §5 D3 (model routing)

### LLD
- docs/llds/chat.md (created 2026-03-14)

### EARS
- docs/specs/chat-specs.md (35 specs: 31 active, 4 deferred)

### Tests
- tests/api/test_chat_routing.py
- tests/api/test_rag_pipeline.py
- tests/api/test_citations.py

### Code
- src/api/chat/route.ts — Next.js API route for chat endpoint
- src/lib/rag.ts — retrieval-augmented generation pipeline
- src/lib/router.ts — model routing heuristic (free vs. frontier)
- src/lib/citations.ts — source attribution and link generation
- src/components/ChatInterface.tsx — chat UI component

## Architecture

**Purpose:** Accept plain-language questions from residents, retrieve relevant legal documents, generate accurate answers with source citations, and route to the appropriate model tier based on query complexity.

**Key Components:**
1. Query preprocessor — extract jurisdiction hints, topic keywords, complexity signals
2. Vector retrieval — pgvector similarity search filtered by jurisdiction/type metadata
3. Model router — heuristic classifier: multi-jurisdiction/impact queries → Claude API; everything else → Gemini Flash
4. Prompt constructor — system prompt with legal context, retrieved chunks, citation instructions
5. Citation generator — map response claims back to source documents with links
6. Legal disclaimer — every response includes non-legal-advice disclaimer

## EARS Coverage

See spec file in References above.

## Key Findings

None yet — UNMAPPED.

## Work Required

### Must Fix
1. RAG pipeline: query → embed → retrieve top-k chunks → construct prompt → call model → return response
2. Model routing heuristic (keyword/intent classification for tier selection)
3. Citation linking (map retrieved chunks to source URLs)
4. Legal disclaimer injection on every response
5. Chat UI component with streaming response display

### Should Fix
1. Conversation context (multi-turn: "what about for commercial properties?" should carry forward "fence" context)
2. "I don't know" handling — detect low retrieval confidence, admit uncertainty rather than hallucinate
3. Jurisdiction disambiguation ("the county" vs. "the town" when both have relevant law)

### Nice to Have
1. Query suggestion / autocomplete based on common questions
2. Feedback mechanism (thumbs up/down on responses for quality tracking)
3. Response caching for repeated common questions
