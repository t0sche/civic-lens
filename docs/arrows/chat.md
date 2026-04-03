# Arrow: chat

RAG-powered Q&A interface: query understanding, vector retrieval, model routing, prompt construction, citation generation, and legal disclaimers.

## Status

**IMPLEMENTED** - 2026-03-19. Full RAG pipeline, model routing, citation generation, legal disclaimers, and chat UI all shipped in Phases 5–7.

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

- `src/app/api/chat/route.ts` — POST /api/chat; validates message (empty/length); calls RAG pipeline; returns JSON with answer, sources, model, tier, routingReason
- `src/lib/rag.ts` — full RAG pipeline: embeds query via Gemini, retrieves top-k chunks via `match_document_chunks`, builds system prompt with numbered sources and legal disclaimer, routes to Claude Sonnet or Gemini Flash
- `src/lib/router.ts` — routes to frontier model when chunks span ≥3 source docs, multiple jurisdictions, or query matches complexity signal patterns
- `src/lib/citations.ts` — maps retrieved chunks to source URLs for clickable citations
- `src/components/ChatInterface.tsx` — chat UI with example questions, loading indicator, source citations, model tier badge, and legal disclaimer
- All 27 active specs (CHAT-RAG through CHAT-UI) verified implemented; multi-turn context (CHAT-CTX) and quality safeguards (CHAT-QUAL) deferred
- **Security gap**: POST /api/chat has no rate limiting; endpoint calls Claude Sonnet (paid) on every request — trivial API cost abuse possible

## Work Required

### Phase 9
1. Rate limiting on /api/chat (Upstash or Vercel Edge middleware — 10 req/min/IP)
2. EARS specs for Stats API: DASH-STATS-001 through 005 (GET /api/stats contract)
3. Jest test coverage for rag.ts pipeline (test_rag_pipeline.py placeholder listed in References but not created)
