/**
 * AI Summary generation API for legislative items.
 *
 * GET /api/legislation/[id]/summary
 *
 * Returns a JSON response with an AI-generated summary containing
 * inline citations from the source document. Caches the result in
 * the legislative_items.ai_summary JSONB column.
 */

import { NextRequest, NextResponse } from "next/server";
import { generateText } from "ai";
import { createServerClient } from "@/lib/supabase-client";
import { retrieveContext } from "@/lib/rag";
import { getModel } from "@/lib/router";

interface Citation {
  index: number;
  quote: string;
  source: string;
}

interface AISummary {
  text: string;
  citations: Citation[];
  generated_at: string;
}

interface RouteParams {
  params: Promise<{ id: string }>;
}

export async function GET(request: NextRequest, { params }: RouteParams) {
  const { id } = await params;

  if (!id || !/^[0-9a-f-]{36}$/i.test(id)) {
    return NextResponse.json({ error: "Invalid item ID" }, { status: 400 });
  }

  const db = createServerClient();

  // Fetch the legislative item
  const { data: item, error: itemError } = await db
    .from("legislative_items")
    .select("*, bronze_documents(raw_content, raw_metadata)")
    .eq("id", id)
    .single();

  if (itemError || !item) {
    return NextResponse.json(
      { error: "Legislative item not found" },
      { status: 404 }
    );
  }

  // Return cached summary if available
  if (item.ai_summary) {
    return NextResponse.json({
      ...item.ai_summary,
      cached: true,
    });
  }

  // Gather source text for the LLM
  const sourceTexts: { label: string; text: string }[] = [];
  const MAX_CONTEXT_CHARS = 20000;
  let totalChars = 0;

  // Launch parallel fetches: direct chunks + source URL content (if needed)
  const chunksPromise = db
    .from("document_chunks")
    .select("chunk_text, section_path, metadata")
    .eq("source_id", id)
    .order("chunk_index", { ascending: true });

  // Also kick off a vector search using the title as query for related context
  const ragPromise = retrieveContext(item.title, {
    topK: 6,
    jurisdiction: item.jurisdiction,
  });

  // Try fetching source_url content when bronze is thin (common for municipal PDFs/HTML)
  const bronzeText = extractBronzeText(item.bronze_documents?.raw_content);
  const sourceUrlPromise =
    bronzeText.length < 500 && item.source_url
      ? fetchSourceContent(item.source_url)
      : Promise.resolve(null);

  // 1. Bronze raw content
  if (bronzeText.length > 100) {
    const text = bronzeText.slice(0, 12000);
    sourceTexts.push({
      label: `Original document: ${item.source_id}`,
      text,
    });
    totalChars += text.length;
  }

  // 2. Source URL content (when bronze was thin)
  const sourceUrlContent = await sourceUrlPromise;
  if (sourceUrlContent && totalChars < MAX_CONTEXT_CHARS) {
    const text = sourceUrlContent.slice(0, 12000);
    sourceTexts.push({
      label: `Fetched from source: ${item.source_id}`,
      text,
    });
    totalChars += text.length;
  }

  // 3. Document chunks linked to this item
  const { data: chunks } = await chunksPromise;
  if (chunks) {
    for (const chunk of chunks) {
      if (totalChars >= MAX_CONTEXT_CHARS) break;
      const text = chunk.chunk_text.slice(0, 4000);
      sourceTexts.push({
        label: chunk.section_path || "Related section",
        text,
      });
      totalChars += text.length;
    }
  }

  // 4. RAG-retrieved related context (code sections, related legislation)
  const ragContext = await ragPromise;
  if (ragContext.chunks.length > 0 && totalChars < MAX_CONTEXT_CHARS) {
    for (const chunk of ragContext.chunks) {
      if (totalChars >= MAX_CONTEXT_CHARS) break;
      // Skip chunks that are just the item's own title+summary (already have that)
      if (chunk.source_id === id) continue;
      const text = chunk.chunk_text.slice(0, 4000);
      sourceTexts.push({
        label: chunk.section_path || `Related: ${chunk.source_type} (${chunk.jurisdiction})`,
        text,
      });
      totalChars += text.length;
    }
  }

  // If we have no source text at all, return a message
  if (sourceTexts.length === 0) {
    return NextResponse.json({
      text: "No source documents are available yet for this legislative item. A summary will be generated once the full text has been ingested into our system.",
      citations: [],
      generated_at: new Date().toISOString(),
      cached: false,
      no_sources: true,
    });
  }

  // Build the prompt
  const contextBlock = sourceTexts
    .map(
      (s, i) =>
        `[Source ${i + 1}: ${s.label}]\n${s.text}`
    )
    .join("\n\n---\n\n");

  const systemPrompt = `You are CivicLens, a civic transparency assistant. Generate a clear, plain-language summary of the following legislative item for residents.

RULES:
1. Write a comprehensive but accessible summary (3-6 paragraphs).
2. Use inline citations in [N] format to reference specific passages from the source documents.
3. After the summary, output a CITATIONS section in exactly this format:
   ---CITATIONS---
   [1] "exact quoted text from source" — Source label
   [2] "exact quoted text from source" — Source label
4. Each citation must quote text that actually appears in the sources provided.
5. Use plain language. Explain legal terms when you use them.
6. Cover: what the legislation does, who it affects, key provisions, and current status.
7. Do NOT provide legal advice.

LEGISLATIVE ITEM:
Title: ${item.title}
Type: ${item.item_type}
Status: ${item.status}
Jurisdiction: ${item.jurisdiction}
Body: ${item.body}
${item.sponsors?.length ? `Sponsors: ${item.sponsors.join(", ")}` : ""}
${item.last_action ? `Last Action: ${item.last_action} (${item.last_action_date})` : ""}

SOURCE DOCUMENTS:
${contextBlock}`;

  try {
    // Always use frontier model for summary quality
    const routing = {
      tier: "frontier" as const,
      model: "claude-sonnet-4-6",
      reason: "Summary generation requires high-quality reasoning",
      questionType: "synthesis" as const,
    };

    const result = await generateText({
      model: getModel(routing),
      system: systemPrompt,
      messages: [
        {
          role: "user",
          content:
            "Generate a comprehensive plain-language summary of this legislative item with citations.",
        },
      ],
      maxOutputTokens: 2048,
    });

    const fullText = result.text;

    // Parse citations from the response
    const citationSplit = fullText.split("---CITATIONS---");
    const summaryText = citationSplit[0].trim();
    const citations: Citation[] = [];

    if (citationSplit[1]) {
      const citationLines = citationSplit[1].trim().split("\n");
      for (const line of citationLines) {
        const match = line.match(
          /^\[(\d+)\]\s*"([^"]+)"\s*(?:—|--|-)\s*(.+)$/
        );
        if (match) {
          citations.push({
            index: parseInt(match[1]),
            quote: match[2],
            source: match[3].trim(),
          });
        }
      }
    }

    const aiSummary: AISummary = {
      text: summaryText,
      citations,
      generated_at: new Date().toISOString(),
    };

    // Cache the summary in the database
    await db
      .from("legislative_items")
      .update({ ai_summary: aiSummary })
      .eq("id", id);

    return NextResponse.json({ ...aiSummary, cached: false });
  } catch (error) {
    console.error("Summary generation error:", error);
    return NextResponse.json(
      {
        error: "Failed to generate summary. Please try again later.",
        detail: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}

/** Extract usable text from bronze raw_content (may be HTML, JSON, or plain text). */
function extractBronzeText(rawContent: string | null | undefined): string {
  if (!rawContent) return "";
  // If it looks like JSON (from belair_legislation scraper), parse and extract title
  if (rawContent.startsWith("{")) {
    try {
      const parsed = JSON.parse(rawContent);
      return [parsed.title, parsed.number, parsed.status]
        .filter(Boolean)
        .join(" — ");
    } catch {
      // fall through to HTML/text handling
    }
  }
  // Strip HTML tags
  return rawContent.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

/** Fetch text content from a source URL. Returns null on failure or for PDFs. */
async function fetchSourceContent(url: string): Promise<string | null> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);

    const res = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent": "CivicLens/1.0 (civic transparency tool)",
        Accept: "text/html, text/plain, application/xhtml+xml",
      },
    });
    clearTimeout(timeout);

    if (!res.ok) return null;

    const contentType = res.headers.get("content-type") || "";

    // Can't parse PDFs without a library — skip
    if (contentType.includes("application/pdf")) return null;

    // For HTML/text responses, extract text
    if (
      contentType.includes("text/html") ||
      contentType.includes("text/plain") ||
      contentType.includes("application/xhtml")
    ) {
      const html = await res.text();
      // Extract body content, strip tags, collapse whitespace
      const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
      const content = bodyMatch ? bodyMatch[1] : html;
      // Remove script/style blocks first
      const cleaned = content
        .replace(/<script[\s\S]*?<\/script>/gi, "")
        .replace(/<style[\s\S]*?<\/style>/gi, "")
        .replace(/<[^>]*>/g, " ")
        .replace(/\s+/g, " ")
        .trim();
      // Only return if we got meaningful content (not just nav/footer boilerplate)
      return cleaned.length > 200 ? cleaned : null;
    }

    return null;
  } catch {
    return null;
  }
}
