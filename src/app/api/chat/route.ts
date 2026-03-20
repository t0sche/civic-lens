/**
 * Chat API route — handles user questions about local law.
 *
 * POST /api/chat
 * Body: { message: string, jurisdiction?: string }
 *
 * Returns a streaming text response with custom headers for metadata.
 * Non-streaming fallback: JSON response with { answer, sources, model, tier, routingReason, questionType }
 *
 * @spec CHAT-API-001, CHAT-RLMT-001, CHAT-RLMT-002, CHAT-RLMT-003, CHAT-RLMT-004
 */

import { NextRequest, NextResponse } from "next/server";
import { streamText } from "ai";
import { retrieveContext, buildPrompt, type RetrievedChunk } from "@/lib/rag";
import { routeQuery, getModel } from "@/lib/router";
import { checkRateLimit } from "@/lib/rate-limit";

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
  data_source?: string;
  url: string | null;
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

    // @spec CHAT-RLMT-001 — enforce per-IP hourly request limit
    const rateLimit = await checkRateLimit(request);
    const rateLimitHeaders = {
      "X-RateLimit-Limit": String(rateLimit.limit),
      "X-RateLimit-Remaining": String(rateLimit.remaining),
      "X-RateLimit-Reset": String(rateLimit.resetAt),
    };

    if (!rateLimit.allowed) {
      return NextResponse.json(
        {
          error:
            "Too many requests. Please wait before asking another question.",
        },
        {
          status: 429,
          headers: {
            ...rateLimitHeaders,
            "Retry-After": String(
              Math.max(0, rateLimit.resetAt - Math.floor(Date.now() / 1000))
            ),
          },
        }
      );
    }

    // Step 1: Retrieve relevant context
    const context = await retrieveContext(body.message, {
      jurisdiction: body.jurisdiction,
    });

    // Step 2: Route to appropriate model based on question type + retrieval signals
    const routing = routeQuery(body.message, context);

    // Step 3: Build prompt with context
    const { system, user } = buildPrompt(body.message, context);

    // Step 4: Format sources
    const sources: Source[] = context.chunks.map(
      (chunk: RetrievedChunk, i: number) => ({
        index: i + 1,
        section_path: chunk.section_path,
        jurisdiction: chunk.jurisdiction,
        source_type: chunk.source_type,
        similarity: Math.round(chunk.similarity * 100) / 100,
        data_source: (chunk.metadata?.source as string) || undefined,
        url: chunk.source_url ?? null,
      })
    );

    // Step 5: Stream the response using AI SDK
    const result = streamText({
      model: getModel(routing),
      system,
      messages: [{ role: "user", content: user }],
      maxOutputTokens: 2048,
    });

    // Return a streaming response with metadata in custom headers
    return result.toTextStreamResponse({
      headers: {
        ...rateLimitHeaders,
        "X-Model": routing.model,
        "X-Tier": routing.tier,
        "X-Question-Type": routing.questionType,
        "X-Routing-Reason": routing.reason,
        "X-Sources": JSON.stringify(sources),
      },
    });
  } catch (error) {
    console.error("Chat API error:", error);
    return NextResponse.json(
      {
        error:
          "An error occurred while processing your question. Please try again.",
        detail: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}
