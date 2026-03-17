/**
 * Model routing heuristic for chat queries.
 *
 * Routes queries to either a free model (Gemini Flash) for simple questions
 * or a frontier model (Claude Sonnet) for complex multi-document reasoning.
 *
 * Design decision (HLD D3): Heuristic-based routing over cascade or user-triggered.
 * The router examines both the query text and the retrieval context to decide.
 *
 * @spec CHAT-ROUTE-001, CHAT-ROUTE-002
 */

import type { RAGContext } from "./rag";

export type ModelTier = "free" | "frontier";

export interface RoutingDecision {
  tier: ModelTier;
  model: string;
  reason: string;
}

// Keywords and patterns that signal complex queries needing frontier models
const COMPLEXITY_SIGNALS = [
  // Multi-jurisdiction reasoning
  /state\s+(and|vs\.?|versus)\s+(county|town|municipal)/i,
  /county\s+(and|vs\.?|versus)\s+(state|town|municipal)/i,
  /all\s+(three|3)\s+(levels?|jurisdictions?|governments?)/i,
  /which\s+(government|jurisdiction|level)/i,
  // Impact analysis
  /how\s+(would|does|will|could|might)\s+.+\s+affect/i,
  /what\s+(is|are)\s+the\s+(impact|effect|consequence)/i,
  /interact\s+with/i,
  /conflict\s+(with|between)/i,
  /preempt/i,
  /override/i,
  // Comparative / synthesis queries
  /compare|comparison|difference\s+between/i,
  /what\s+are\s+all\s+the/i,
  /comprehensive|exhaustive|complete\s+(list|overview)/i,
  // Complex conditional reasoning
  /if\s+.+\s+then\s+what/i,
  /under\s+what\s+circumstances/i,
  /what\s+are\s+my\s+options/i,
];

/**
 * Determine which model tier should handle a query.
 *
 * @spec CHAT-ROUTE-001
 */
export function routeQuery(
  query: string,
  context: RAGContext
): RoutingDecision {
  const docThreshold = parseInt(
    process.env.MODEL_ROUTING_DOC_THRESHOLD ?? "3"
  );

  // Check 1: Retrieval context spans many distinct documents
  if (context.uniqueDocCount >= docThreshold) {
    return {
      tier: "frontier",
      model: "claude-sonnet-4-6",
      reason: `Retrieved chunks span ${context.uniqueDocCount} distinct documents (threshold: ${docThreshold})`,
    };
  }

  // Check 2: Context spans multiple jurisdictions
  if (context.jurisdictions.length > 1) {
    return {
      tier: "frontier",
      model: "claude-sonnet-4-6",
      reason: `Query involves ${context.jurisdictions.length} jurisdictions: ${context.jurisdictions.join(", ")}`,
    };
  }

  // Check 3: Query text contains complexity signals
  for (const pattern of COMPLEXITY_SIGNALS) {
    if (pattern.test(query)) {
      return {
        tier: "frontier",
        model: "claude-sonnet-4-6",
        reason: `Query matches complexity pattern: ${pattern.source.slice(0, 40)}...`,
      };
    }
  }

  // Default: free model for simple, single-source queries
  return {
    tier: "free",
    model: "gemini-2.0-flash",
    reason: "Simple query with single-jurisdiction context",
  };
}

/**
 * Call the appropriate model API based on the routing decision.
 *
 * @spec CHAT-ROUTE-002
 */
export async function callModel(
  systemPrompt: string,
  userMessage: string,
  routing: RoutingDecision
): Promise<string> {
  if (routing.tier === "frontier") {
    return callClaude(systemPrompt, userMessage, routing.model);
  } else {
    return callGemini(systemPrompt, userMessage);
  }
}

async function callClaude(
  system: string,
  user: string,
  model: string
): Promise<string> {
  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": process.env.ANTHROPIC_API_KEY!,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model,
      max_tokens: 2048,
      system,
      messages: [{ role: "user", content: user }],
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Claude API error (${response.status}): ${errorText}`);
  }

  const data = await response.json();
  return data.content
    .filter((block: any) => block.type === "text")
    .map((block: any) => block.text)
    .join("\n");
}

async function callGemini(system: string, user: string): Promise<string> {
  const apiKey = process.env.GOOGLE_AI_API_KEY!;
  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key=${apiKey}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        systemInstruction: { parts: [{ text: system }] },
        contents: [{ parts: [{ text: user }] }],
        generationConfig: { maxOutputTokens: 2048 },
      }),
    }
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Gemini API error (${response.status}): ${errorText}`);
  }

  const data = await response.json();
  return (
    data.candidates?.[0]?.content?.parts
      ?.map((p: any) => p.text)
      .join("\n") ?? "I was unable to generate a response."
  );
}
