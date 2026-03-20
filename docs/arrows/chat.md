# Arrow: chat

RAG-powered Q&A interface: query understanding, vector retrieval, model routing, prompt construction, citation generation, and legal disclaimers.

## Status

**IMPLEMENTED** - 2026-03-20. RAG pipeline, model routing, streaming responses, citation generation, and rate limiting are live. Chat UI is functional at /chat.

## References

### HLD
- docs/high-level-design.md §4.1 (Chat Interface box), §4.2 (Chat model rows), §5 D3 (model routing)

### LLD
- docs/llds/chat.md (created 2026-03-14)

### EARS
- docs/specs/chat-specs.md (39 specs: 35 active, 4 deferred)

### Tests
- tests/api/test_chat_route.py — request validation, routing, and response shape
- tests/api/test_chat_rate_limit.py — rate limiting logic

### Code
- src/app/api/chat/route.ts — Next.js API route for chat endpoint (with rate limiting)
- src/lib/rag.ts — retrieval-augmented generation pipeline
- src/lib/router.ts — model routing heuristic (free vs. frontier)
- src/lib/rate-limit.ts — per-IP hourly rate limiting via Supabase
- src/app/chat/page.tsx — chat UI component
- supabase/migrations/005_rate_limits.sql — rate_limits table and increment RPC

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

- Chat API, RAG pipeline, model routing, and streaming responses are fully implemented.
- Rate limiting (CHAT-RLMT-001 through CHAT-RLMT-004) implemented in Phase 9 using Supabase-backed per-IP hourly counters.
- Stats API and Stats page shipped without EARS specs (DASH-STATS-001 through 005 still needed).
- TS RAG pipeline and chat UI lack Jest test coverage.

## Work Required

### Should Fix
1. Conversation context (multi-turn: "what about for commercial properties?" should carry forward "fence" context)
2. "I don't know" handling — detect low retrieval confidence, admit uncertainty rather than hallucinate
3. Stats API EARS specs (DASH-STATS-001 through 005)
4. Jest test coverage for RAG pipeline and chat UI

### Nice to Have
1. Query suggestion / autocomplete based on common questions
2. Feedback mechanism (thumbs up/down on responses for quality tracking)
3. Response caching for repeated common questions
