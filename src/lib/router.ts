/**
 * Model routing with question-type classification.
 *
 * Routes queries to either a free model (Gemini Flash) for simple questions
 * or a frontier model (Claude Sonnet) for complex multi-document reasoning.
 *
 * Routing strategy (three-signal approach):
 * 1. Question type — classified from query text patterns
 * 2. Retrieval signals — doc count, jurisdictions, avg similarity
 * 3. Complexity patterns — regex fallback for edge cases
 *
 * Design decision (HLD D3): Heuristic-based routing over cascade or user-triggered.
 * False positives (routing simple to frontier) waste money but don't harm quality.
 * False negatives (routing complex to free) produce lower-quality answers.
 *
 * @spec CHAT-ROUTE-001, CHAT-ROUTE-002
 */

import { google } from "@ai-sdk/google";
import { anthropic } from "@ai-sdk/anthropic";
import type { RAGContext } from "./rag";

export type ModelTier = "free" | "frontier";

/**
 * Question types that drive routing decisions.
 *
 * Simple types (→ Gemini Flash, free):
 * - factual_lookup: "What is the fence height limit?"
 * - definition: "What does 'setback' mean?"
 * - status_check: "What is the status of HB 1234?"
 * - procedural: "How do I apply for a building permit?"
 *
 * Complex types (→ Claude Sonnet, frontier):
 * - comparison: "How do state and county noise rules differ?"
 * - analysis: "How would HB 1234 affect Bel Air zoning?"
 * - multi_jurisdiction: "What are all the regulations about fences across all levels?"
 * - synthesis: "Give me a comprehensive overview of property regulations"
 */
export type QuestionType =
  | "factual_lookup"
  | "definition"
  | "status_check"
  | "procedural"
  | "comparison"
  | "analysis"
  | "multi_jurisdiction"
  | "synthesis";

const SIMPLE_TYPES: QuestionType[] = [
  "factual_lookup",
  "definition",
  "status_check",
  "procedural",
];

export interface RoutingDecision {
  tier: ModelTier;
  model: string;
  reason: string;
  questionType: QuestionType;
}

// --- Question type classification patterns ---

const DEFINITION_PATTERNS = [
  /what\s+(does|is)\s+(a|an|the)?\s*["']?\w+["']?\s+(mean|refer\s+to|stand\s+for)/i,
  /define\s+/i,
  /definition\s+of/i,
  /what\s+is\s+(a|an|the)\s+\w+\??$/i,
];

const STATUS_PATTERNS = [
  /status\s+of/i,
  /what\s+happened\s+(to|with)/i,
  /where\s+is\s+.+\s+(in\s+the\s+process|now)/i,
  /has\s+.+\s+(passed|been\s+(signed|vetoed|introduced|approved))/i,
  /is\s+.+\s+still\s+(active|pending|in\s+committee)/i,
];

const PROCEDURAL_PATTERNS = [
  /how\s+(do|can|should)\s+I\s+(apply|file|submit|request|get|obtain|register)/i,
  /what\s+(is|are)\s+the\s+(process|steps|procedure|requirements?)\s+(for|to)/i,
  /where\s+(do|can)\s+I\s+(go|apply|file|submit)/i,
  /who\s+(do|should)\s+I\s+(contact|call|email)/i,
];

const COMPARISON_PATTERNS = [
  /compare|comparison|difference\s+between/i,
  /state\s+(and|vs\.?|versus)\s+(county|town|municipal)/i,
  /county\s+(and|vs\.?|versus)\s+(state|town|municipal)/i,
  /how\s+(does|do)\s+.+\s+differ/i,
  /which\s+(is|are)\s+(more|less|stricter|looser)/i,
];

const ANALYSIS_PATTERNS = [
  /how\s+(would|does|will|could|might)\s+.+\s+affect/i,
  /what\s+(is|are)\s+the\s+(impact|effect|consequence)/i,
  /interact\s+with/i,
  /conflict\s+(with|between)/i,
  /preempt/i,
  /override/i,
  /if\s+.+\s+then\s+what/i,
  /under\s+what\s+circumstances/i,
  /what\s+are\s+my\s+options/i,
];

const MULTI_JURISDICTION_PATTERNS = [
  /all\s+(three|3)\s+(levels?|jurisdictions?|governments?)/i,
  /which\s+(government|jurisdiction|level)/i,
  /across\s+(all|every|multiple)\s+(levels?|jurisdictions?)/i,
  /at\s+(each|every)\s+level/i,
];

const SYNTHESIS_PATTERNS = [
  /what\s+are\s+all\s+the/i,
  /comprehensive|exhaustive|complete\s+(list|overview|summary)/i,
  /everything\s+(about|regarding|related\s+to)/i,
  /summarize\s+all/i,
  /full\s+(overview|picture|breakdown)/i,
];

/**
 * Classify a query into a question type based on text patterns.
 *
 * @spec CHAT-ROUTE-003
 */
export function classifyQuestion(query: string): QuestionType {
  // Check complex types first (they're more specific)
  for (const pattern of MULTI_JURISDICTION_PATTERNS) {
    if (pattern.test(query)) return "multi_jurisdiction";
  }
  for (const pattern of COMPARISON_PATTERNS) {
    if (pattern.test(query)) return "comparison";
  }
  for (const pattern of ANALYSIS_PATTERNS) {
    if (pattern.test(query)) return "analysis";
  }
  for (const pattern of SYNTHESIS_PATTERNS) {
    if (pattern.test(query)) return "synthesis";
  }

  // Then simple types
  for (const pattern of DEFINITION_PATTERNS) {
    if (pattern.test(query)) return "definition";
  }
  for (const pattern of STATUS_PATTERNS) {
    if (pattern.test(query)) return "status_check";
  }
  for (const pattern of PROCEDURAL_PATTERNS) {
    if (pattern.test(query)) return "procedural";
  }

  // Default: factual lookup (cheapest assumption)
  return "factual_lookup";
}

/**
 * Determine which model tier should handle a query.
 *
 * Three-signal routing:
 * 1. Question type classification (text patterns)
 * 2. Retrieval signals (doc count, jurisdictions, avg similarity)
 * 3. Confidence override — high-confidence single-source answers
 *    stay on free tier even if question type suggests complexity
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
  const questionType = classifyQuestion(query);
  const isComplexType = !SIMPLE_TYPES.includes(questionType);

  // Signal 1: Retrieval context spans many distinct documents
  if (context.uniqueDocCount >= docThreshold) {
    return {
      tier: "frontier",
      model: "claude-sonnet-4-6",
      reason: `Retrieved chunks span ${context.uniqueDocCount} distinct documents (threshold: ${docThreshold})`,
      questionType,
    };
  }

  // Signal 2: Context spans multiple jurisdictions
  if (context.jurisdictions.length > 1) {
    return {
      tier: "frontier",
      model: "claude-sonnet-4-6",
      reason: `Query involves ${context.jurisdictions.length} jurisdictions: ${context.jurisdictions.join(", ")}`,
      questionType,
    };
  }

  // Signal 3: Question type indicates complexity
  if (isComplexType) {
    // Confidence override: if retrieval returned high-confidence results
    // from a single source, the free model can handle it — the RAG context
    // is strong enough that the model just needs to summarize, not reason.
    if (
      context.avgSimilarity >= 0.7 &&
      context.uniqueDocCount <= 1 &&
      context.jurisdictions.length <= 1
    ) {
      return {
        tier: "free",
        model: "gemini-2.0-flash",
        reason: `Question type "${questionType}" but high-confidence single-source retrieval (avg similarity: ${context.avgSimilarity.toFixed(2)}) — free model sufficient`,
        questionType,
      };
    }

    return {
      tier: "frontier",
      model: "claude-sonnet-4-6",
      reason: `Question type "${questionType}" requires deeper reasoning`,
      questionType,
    };
  }

  // Default: free model for simple question types with narrow context
  return {
    tier: "free",
    model: "gemini-2.0-flash",
    reason: `Simple "${questionType}" query with single-jurisdiction context`,
    questionType,
  };
}

/**
 * Get the AI SDK model instance for a routing decision.
 *
 * @spec CHAT-MODEL-001, CHAT-MODEL-002
 */
export function getModel(routing: RoutingDecision) {
  if (routing.tier === "frontier") {
    return anthropic("claude-sonnet-4-6");
  }
  return google("gemini-2.0-flash");
}
