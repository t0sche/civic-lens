# Arrow: chat

RAG-powered Q&A interface: query understanding, vector retrieval, model routing, prompt construction, citation generation, and legal disclaimers.

## Status

**IMPLEMENTED** - 2026-03-19. route.ts, rag.ts, router.ts, citations.ts, and ChatInterface.tsx are fully built and deployed.

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

As of 2026-03-19:
- **route.ts** — POST /api/chat with 2000-char input validation and streaming via AI SDK `streamText`; no rate limiting (open API cost exposure — Phase 9 priority)
- **router.ts** — 8-type `QuestionType` classifier (`classifyQuestion()`, `routeQuery()`); simple → Gemini Flash, complex/multi-jurisdiction → Claude Sonnet
- **rag.ts** — `buildPrompt()` constructs system prompt with retrieved chunks, jurisdiction context, and legal disclaimer injected on every response
- **citations.ts** — source attribution maps retrieved chunks to source URLs
- **Stats API** (`/api/stats`, `/stats` page) shipped without EARS specs — DASH-STATS-001 through 005 needed
- CSP `connect-src` (next.config.js:26) does not include `generativelanguage.googleapis.com` or `api.anthropic.com` — currently safe (server-only calls), but fragile if any AI call moves client-side
- No Jest test coverage for router.ts or rag.ts pure functions

## Work Required (Post-MVP)

### Phase 9
1. Rate limiting on POST /api/chat — IP-based via Upstash ratelimit or Vercel Edge middleware
2. DASH-STATS-001 through 005 EARS specs for Stats API
3. Jest/Vitest unit tests for `classifyQuestion()`, `routeQuery()`, `buildPrompt()`
4. Conversation context (multi-turn carry-forward)
5. Low-confidence "I don't know" detection
