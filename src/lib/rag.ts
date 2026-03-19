/**
 * RAG (Retrieval-Augmented Generation) pipeline for the chat interface.
 *
 * Workflow:
 * 1. Embed the user query
 * 2. Search pgvector for similar document chunks (filtered by jurisdiction)
 * 3. Construct a prompt with retrieved context
 * 4. Route to the appropriate model (free or frontier)
 * 5. Generate response with source citations
 *
 * @spec CHAT-RAG-001, CHAT-RAG-002, CHAT-RAG-003
 */

import { createServerClient } from "./supabase-client";

export interface RetrievedChunk {
  id: string;
  chunk_text: string;
  section_path: string | null;
  jurisdiction: string;
  source_type: string;
  source_id: string;
  similarity: number;
  metadata: Record<string, unknown>;
}

export interface RAGContext {
  chunks: RetrievedChunk[];
  uniqueDocCount: number;
  jurisdictions: string[];
  /** Average similarity score across retrieved chunks (0-1). Used for routing confidence. */
  avgSimilarity: number;
}

/**
 * Embed a query string using the Gemini embedding API.
 *
 * @spec CHAT-RAG-001
 */
async function embedQuery(query: string): Promise<number[]> {
  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1/models/text-embedding-004:embedContent?key=${process.env.GOOGLE_AI_API_KEY}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: { parts: [{ text: query }] },
        taskType: "RETRIEVAL_QUERY",
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Embedding API error: ${response.statusText}`);
  }

  const data = await response.json();
  return data.embedding.values;
}

/**
 * Retrieve the most relevant document chunks for a query.
 *
 * Uses pgvector cosine similarity search with optional jurisdiction filtering.
 *
 * @spec CHAT-RAG-002
 */
export async function retrieveContext(
  query: string,
  options: {
    topK?: number;
    jurisdiction?: string;
  } = {}
): Promise<RAGContext> {
  const topK = options.topK ?? parseInt(process.env.RAG_TOP_K ?? "8");
  const db = createServerClient();

  // Step 1: Embed the query
  const queryEmbedding = await embedQuery(query);

  // Step 2: Search pgvector
  // Using Supabase's RPC for vector similarity search
  const { data, error } = await db.rpc("match_document_chunks", {
    query_embedding: queryEmbedding,
    match_threshold: 0.3,
    match_count: topK,
    filter_jurisdiction: options.jurisdiction || null,
  });

  if (error) {
    console.error("Vector search failed:", error);
    return { chunks: [], uniqueDocCount: 0, jurisdictions: [], avgSimilarity: 0 };
  }

  type RpcRow = {
    id: string;
    chunk_text: string;
    section_path: string | null;
    jurisdiction: string;
    source_type: string;
    source_id: string;
    similarity: number;
    metadata: Record<string, unknown> | null;
  };
  const chunks: RetrievedChunk[] = (data || []).map((row: RpcRow) => ({
    id: row.id,
    chunk_text: row.chunk_text,
    section_path: row.section_path,
    jurisdiction: row.jurisdiction,
    source_type: row.source_type,
    source_id: row.source_id,
    similarity: row.similarity,
    metadata: row.metadata || {},
  }));

  // Compute context metadata for model routing
  const uniqueDocIds = new Set(chunks.map((c) => c.source_id));
  const jurisdictions = Array.from(new Set(chunks.map((c) => c.jurisdiction)));
  const avgSimilarity =
    chunks.length > 0
      ? chunks.reduce((sum, c) => sum + c.similarity, 0) / chunks.length
      : 0;

  return {
    chunks,
    uniqueDocCount: uniqueDocIds.size,
    jurisdictions,
    avgSimilarity,
  };
}

/**
 * Build the system prompt with retrieved context for the LLM.
 *
 * @spec CHAT-RAG-004
 */
export function buildPrompt(
  userQuery: string,
  context: RAGContext
): { system: string; user: string } {
  const contextBlock = context.chunks
    .map((chunk, i) => {
      const source = chunk.section_path || `Source ${i + 1}`;
      return `[Source ${i + 1}: ${source} (${chunk.jurisdiction})]
${chunk.chunk_text}`;
    })
    .join("\n\n---\n\n");

  const system = `You are CivicLens, a civic transparency assistant for Bel Air, Maryland (ZIP 21015). You help residents understand the laws, ordinances, and regulations that affect them across three levels of government: Maryland State, Harford County, and the Town of Bel Air.

RULES:
1. Answer based ONLY on the provided source documents. If the sources don't contain the answer, say so clearly.
2. Cite your sources using [Source N] notation. Every factual claim must have a citation.
3. Use plain language. Avoid legal jargon unless quoting directly from a law.
4. When laws from different jurisdictions are relevant, explain which level of government each comes from.
5. If asked for legal advice, remind the user that you provide information about laws, not legal advice, and suggest consulting an attorney for specific legal questions.
6. If the question is about a topic not covered in the sources, say so and suggest where the user might find the answer (e.g., "This may be covered by state regulations (COMAR), which are not yet in our database").

IMPORTANT: You are NOT a lawyer. Always include this disclaimer at the end of substantive answers:
"This information is for educational purposes only and is not legal advice. Consult a qualified attorney for legal guidance."

CONTEXT DOCUMENTS:
${contextBlock || "No relevant documents found for this query."}`;

  return { system, user: userQuery };
}
