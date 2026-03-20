# Chat Specifications

**Design Doc**: `/docs/llds/chat.md`
**Arrow**: `/docs/arrows/chat.md`

## RAG Pipeline

- [ ] **CHAT-RAG-001**: When a user submits a question, the system shall embed the query using the same embedding model and task type (RETRIEVAL_QUERY) used for document indexing.
- [ ] **CHAT-RAG-002**: The system shall retrieve the top-k most similar document chunks from pgvector, where k defaults to the RAG_TOP_K environment variable (default 8).
- [ ] **CHAT-RAG-003**: When a jurisdiction filter is provided in the request, the system shall pass it to the vector search function to scope retrieval to that jurisdiction.
- [ ] **CHAT-RAG-004**: The system shall construct a prompt containing: a system instruction defining CivicLens's role and rules, the retrieved chunks formatted as numbered sources with jurisdiction and section_path labels, and the user's question.

## System Prompt Rules

- [ ] **CHAT-RAG-010**: The system prompt shall instruct the model to answer only from the provided source documents and to state clearly when sources do not contain the answer.
- [ ] **CHAT-RAG-011**: The system prompt shall instruct the model to cite sources using [Source N] notation, requiring every factual claim to have a citation.
- [ ] **CHAT-RAG-012**: The system prompt shall instruct the model to use plain language and avoid legal jargon unless quoting directly from a law.
- [ ] **CHAT-RAG-013**: The system prompt shall instruct the model to identify which jurisdiction each cited source belongs to when sources from multiple jurisdictions are retrieved.
- [ ] **CHAT-RAG-014**: The system prompt shall instruct the model to include this disclaimer at the end of every substantive answer: "This information is for educational purposes only and is not legal advice. Consult a qualified attorney for legal guidance."
- [ ] **CHAT-RAG-015**: When no relevant chunks are retrieved (all below similarity threshold), the system prompt shall instruct the model to state that it does not have information on that topic and suggest where to look.

## Model Routing

- [ ] **CHAT-ROUTE-001**: When retrieved chunks span 3 or more distinct source documents (configurable via MODEL_ROUTING_DOC_THRESHOLD), the system shall route the query to the frontier model (Claude Sonnet).
- [ ] **CHAT-ROUTE-002**: When retrieved chunks span multiple jurisdictions, the system shall route the query to the frontier model.
- [ ] **CHAT-ROUTE-003**: When the query text matches any complexity signal pattern (multi-jurisdiction references, impact analysis phrases, comparative language), the system shall route to the frontier model.
- [ ] **CHAT-ROUTE-004**: When none of the frontier routing conditions are met, the system shall route the query to the free model (Gemini Flash).
- [ ] **CHAT-ROUTE-005**: The system shall include the routing decision (tier, model name, reason) in the API response for observability.

## API Contract

- [ ] **CHAT-API-001**: The system shall accept POST requests to /api/chat with a JSON body containing a required `message` string and an optional `jurisdiction` string.
- [ ] **CHAT-API-002**: If the message is empty or missing, then the system shall return HTTP 400 with an error message.
- [ ] **CHAT-API-003**: If the message exceeds 2,000 characters, then the system shall return HTTP 400 with an error message.
- [ ] **CHAT-API-004**: The system shall return a JSON response containing: answer (string), sources (array of objects with index, section_path, jurisdiction, source_type, similarity, url: string|null), model (string), tier (string), and routingReason (string). The url field contains the source_url from the Silver layer for direct linking to the original document.
- [ ] **CHAT-API-005**: If any step of the RAG pipeline fails, then the system shall return HTTP 500 with a user-friendly error message and a detail field for debugging.

## Model Calls

- [ ] **CHAT-MODEL-001**: When calling Claude Sonnet, the system shall use the Anthropic Messages API with the system prompt as the `system` parameter and the user question as a user message.
- [ ] **CHAT-MODEL-002**: When calling Gemini Flash, the system shall use the Gemini generateContent API with the system prompt as `systemInstruction` and the user question as content.
- [ ] **CHAT-MODEL-003**: If a model API call fails, then the system shall propagate the error with the HTTP status and response body for debugging.

## Chat UI

- [ ] **CHAT-UI-001**: The system shall display a chat interface with user messages right-aligned and assistant messages left-aligned.
- [ ] **CHAT-UI-002**: When the conversation is empty, the system shall display at least 4 clickable example questions covering different jurisdictions and query types.
- [ ] **CHAT-UI-003**: When an example question is clicked, the system shall submit it as a query immediately.
- [ ] **CHAT-UI-004**: While a query is being processed, the system shall display a loading indicator with the text "Searching laws and generating answer...".
- [ ] **CHAT-UI-005**: The system shall display source citations below each assistant message, showing the source index, section_path, and jurisdiction for each retrieved chunk.
- [ ] **CHAT-UI-006**: The system shall display a subtle model tier indicator on each assistant message ("Quick answer" for free tier, "Deep analysis" for frontier tier).
- [ ] **CHAT-UI-007**: The system shall display a permanent disclaimer at the bottom of the chat input area stating that CivicLens provides information, not legal advice.
- [ ] **CHAT-UI-008**: The system shall disable the input field and submit button while a query is being processed.

## Conversation Context

- [D] **CHAT-CTX-001**: The system shall support multi-turn conversation by passing the last N messages as context in subsequent API requests.
- [D] **CHAT-CTX-002**: The system shall resolve pronouns and implicit references in follow-up questions by incorporating conversation history into the retrieval query.

## Quality Safeguards

- [D] **CHAT-QUAL-001**: The system shall detect low-confidence retrieval (all chunks below 0.5 similarity) and prepend a caveat to the response indicating the answer may not directly address the question.
- [D] **CHAT-QUAL-002**: The system shall provide a thumbs up/down feedback mechanism on each assistant response for quality tracking.
