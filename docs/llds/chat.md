# Chat: RAG Pipeline and Model Routing

**Created**: 2026-03-14
**Status**: Design Phase
**HLD Reference**: §4.1 Chat Interface, §4.2 Model rows, §5 D3 (model routing)

## Context and Design Philosophy

The chat interface is the primary way residents interact with legal information. The challenge is producing accurate, cited, appropriately disclaimed answers from a corpus of legal text — a domain where hallucination has real consequences.

The design philosophy is **conservative retrieval, honest uncertainty**. The system should prefer "I don't have information about that" over a plausible-sounding but unsupported answer. Every factual claim must cite a retrieved source. The legal disclaimer is not optional.

## RAG Pipeline Architecture

The pipeline executes in five sequential steps for each user query, with a total latency target of <10 seconds (the Vercel serverless function timeout on the free tier).

### Step 1: Query Embedding (~500ms)

The user's question is embedded using the same model that generated the document embeddings (Gemini gemini-embedding-001 with `taskType: RETRIEVAL_QUERY` and `outputDimensionality: 768`). Using the matching task type is important — Gemini optimizes the embedding space differently for documents vs. queries.

### Step 2: Vector Retrieval (~100ms)

The query embedding is passed to the `match_document_chunks` RPC function in Supabase. Default parameters:
- `match_count`: 8 (configurable via `RAG_TOP_K`)
- `match_threshold`: 0.3 (minimum cosine similarity)
- `filter_jurisdiction`: null (search all jurisdictions unless the query specifies one)

The function returns chunks sorted by descending similarity, each with its `section_path`, `jurisdiction`, `source_type`, and `metadata`.

### Step 3: Model Routing (~1ms)

The routing heuristic examines both the query text and the retrieval context to decide which model handles generation:

**Route to Claude API (frontier) when any of:**
- Retrieved chunks span ≥3 distinct source documents (`uniqueDocCount >= MODEL_ROUTING_DOC_THRESHOLD`)
- Retrieved chunks span multiple jurisdictions (`jurisdictions.length > 1`)
- Query text matches complexity signal patterns (multi-jurisdiction references, impact analysis, comparative questions)

**Route to Gemini Flash (free) otherwise:**
- Single-document Q&A
- Definition lookups
- Meeting schedule questions
- Simple status queries

The complexity signal patterns are regular expressions matching phrases like "how would X affect Y", "state and county", "compare", "under what circumstances". These are intentionally conservative — false positives (routing a simple query to Claude) waste money but don't harm quality; false negatives (routing a complex query to Gemini) produce lower-quality answers.

### Step 4: Prompt Construction (~1ms)

The system prompt establishes CivicLens's identity and rules:

1. **Answer only from provided sources** — no training knowledge about Maryland law
2. **Cite sources using [Source N] notation** — every factual claim needs attribution
3. **Plain language** — avoid legal jargon unless quoting directly
4. **Jurisdiction clarity** — when multiple jurisdictions are relevant, label each
5. **No legal advice** — redirect to attorneys for specific legal questions
6. **Honest uncertainty** — if sources don't contain the answer, say so and suggest where to look

The retrieved chunks are formatted as a numbered context block, each labeled with its source path and jurisdiction. The system prompt instructs the model to reference these by number.

### Step 5: Model Call and Response (~3-8s)

**Gemini Flash** (free tier): Typical latency 1-3 seconds. Sufficient for single-source factual answers. The system instruction and content are passed as separate parameters per the Gemini API schema.

**Claude Sonnet** (paid): Typical latency 3-8 seconds. Needed for multi-document synthesis and complex reasoning. Uses the Anthropic Messages API with the system prompt as a separate field.

Both models return the full response text, which is passed directly to the frontend. No post-processing is needed — the citation format ([Source N]) is specified in the system prompt and models follow it reliably.

## Chat API Contract

### Request

```
POST /api/chat
Content-Type: application/json

{
  "message": "What are the fence regulations in Bel Air?",
  "jurisdiction": "MUNICIPAL"  // optional filter
}
```

Validation:
- `message` is required, non-empty, max 2,000 characters
- `jurisdiction` is optional, must be a valid `JurisdictionLevel` value if provided

### Response

```json
{
  "answer": "According to the Town of Bel Air Code...",
  "sources": [
    {
      "index": 1,
      "section_path": "Town of Bel Air Code > Ch. 165 > §165-23",
      "jurisdiction": "MUNICIPAL",
      "source_type": "CODE_SECTION",
      "similarity": 0.82
    }
  ],
  "model": "gemini-2.0-flash",
  "tier": "free",
  "routingReason": "Simple query with single-jurisdiction context"
}
```

The `sources`, `model`, `tier`, and `routingReason` fields support the frontend's citation display and the subtle model tier indicator (for debugging, not prominently displayed to users).

### Error Response

```json
{
  "error": "An error occurred while processing your question.",
  "detail": "Embedding API timeout"  // only in development
}
```

## Conversation Context (Multi-Turn)

MVP chat is **single-turn**: each query is independent. This means a follow-up like "What about for commercial properties?" after asking about fence regulations won't carry the "fence" context.

Multi-turn support is a post-MVP enhancement that requires:
1. Maintaining conversation history in client state
2. Passing the last N messages as context in the API request
3. Including conversation history in the prompt (increases token cost)
4. Handling pronoun resolution ("What about for commercial properties?" → "What are the fence regulations for commercial properties?")

The single-turn limitation should be documented in the UI with a note like "Each question is answered independently. Include full context in your question for best results."

## "I Don't Know" Handling

When the RAG pipeline fails to find relevant context, the system must fail gracefully:

**No chunks retrieved** (all below similarity threshold): The system prompt instructs the model to say "I don't have information about that topic in my current database" and suggest where to look (specific government websites, phone numbers).

**Low-confidence retrieval** (chunks retrieved but similarity < 0.5): The response should include a caveat: "Based on the most relevant documents I found, which may not directly address your question..."

**Topic outside scope**: For questions about federal law, COMAR regulations, or other excluded sources, the system prompt includes explicit redirections: "State regulations (COMAR) are not yet in our database. You can search COMAR directly at dsd.maryland.gov."

## Legal Disclaimer

Every substantive response must end with: "This information is for educational purposes only and is not legal advice. Consult a qualified attorney for legal guidance."

This is enforced in the system prompt, not post-processed. If the model omits it (unlikely but possible), the frontend should append it as a fallback.

## Frontend Chat Interface

### Layout

The chat page uses a standard conversational layout:
- Messages flow vertically, user messages right-aligned (blue), assistant messages left-aligned (white)
- Source citations appear below the assistant message in a collapsed section
- Model tier indicator appears subtly (small badge: "Quick answer" or "Deep analysis")
- Input field is sticky at the bottom with an "Ask" button

### Example Questions

When the conversation is empty, the UI displays 4 clickable example questions that demonstrate the system's capabilities:
- Covers different jurisdictions (town, county, state)
- Covers different query types (regulations, pending legislation, specific code sections)
- Clicking an example populates the input and submits immediately

### Loading State

During the RAG pipeline execution (3-10 seconds), a pulsing indicator with "Searching laws and generating answer..." provides feedback. This is important because 10-second waits without feedback feel broken.

## Open Questions & Future Decisions

### Resolved
1. ✅ Heuristic routing over cascade — predictable, debuggable, no double-latency
2. ✅ Single-turn MVP — multi-turn adds complexity without proportional value at launch
3. ✅ [Source N] citation format — simple, reliable, model-agnostic
4. ✅ Legal disclaimer in system prompt — ensures it's part of the model's response, not an afterthought

### Deferred
1. Multi-turn conversation context — adds pronoun resolution and token cost; defer until user feedback demands it
2. Streaming responses — Vercel supports it, would improve perceived latency for Claude API calls
3. Query suggestion / autocomplete — requires analyzing common queries, defer until there's traffic
4. Feedback mechanism (thumbs up/down) — valuable for quality tracking, low implementation cost, prioritize for Phase 5
5. Response caching — cache common questions (fence regulations, noise ordinance) to avoid repeated API calls

## References

- Gemini API: https://ai.google.dev/gemini-api/docs/
- Anthropic Messages API: https://docs.anthropic.com/en/api/messages
- Vercel streaming: https://vercel.com/docs/functions/streaming
