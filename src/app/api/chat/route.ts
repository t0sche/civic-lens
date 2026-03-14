/**
 * Chat API route — handles user questions about local law.
 *
 * POST /api/chat
 * Body: { message: string, jurisdiction?: string }
 * Response: { answer: string, sources: Source[], model: string, tier: string }
 *
 * @spec CHAT-API-001
 */

import { NextRequest, NextResponse } from "next/server";
import { retrieveContext, buildPrompt, type RetrievedChunk } from "@/lib/rag";
import { routeQuery, callModel } from "@/lib/router";

interface ChatRequest {
  message: string;
  jurisdiction?: string;
}

interface Source {
  index: number;
  section_path: string | null;
  jurisdiction: string;
  source_type: string;
  similarity: number;
}

interface ChatResponse {
  answer: string;
  sources: Source[];
  model: string;
  tier: string;
  routingReason: string;
}

export async function POST(request: NextRequest) {
  try {
    const body: ChatRequest = await request.json();

    if (!body.message || body.message.trim().length === 0) {
      return NextResponse.json(
        { error: "Message is required" },
        { status: 400 }
      );
    }

    if (body.message.length > 2000) {
      return NextResponse.json(
        { error: "Message too long (max 2000 characters)" },
        { status: 400 }
      );
    }

    // Step 1: Retrieve relevant context
    const context = await retrieveContext(body.message, {
      jurisdiction: body.jurisdiction,
    });

    // Step 2: Route to appropriate model
    const routing = routeQuery(body.message, context);

    // Step 3: Build prompt with context
    const { system, user } = buildPrompt(body.message, context);

    // Step 4: Call the model
    const answer = await callModel(system, user, routing);

    // Step 5: Format sources for the response
    const sources: Source[] = context.chunks.map((chunk, i) => ({
      index: i + 1,
      section_path: chunk.section_path,
      jurisdiction: chunk.jurisdiction,
      source_type: chunk.source_type,
      similarity: Math.round(chunk.similarity * 100) / 100,
    }));

    const response: ChatResponse = {
      answer,
      sources,
      model: routing.model,
      tier: routing.tier,
      routingReason: routing.reason,
    };

    return NextResponse.json(response);
  } catch (error) {
    console.error("Chat API error:", error);
    return NextResponse.json(
      {
        error: "An error occurred while processing your question. Please try again.",
        detail: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}
