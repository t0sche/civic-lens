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

  // Gather source text for the LLM — fetch chunks in parallel with bronze processing
  const sourceTexts: { label: string; text: string }[] = [];
  const MAX_CONTEXT_CHARS = 20000;
  let totalChars = 0;

  // Fetch document chunks in parallel while processing bronze content
  const chunksPromise = db
    .from("document_chunks")
    .select("chunk_text, section_path, metadata")
    .eq("source_id", id)
    .order("chunk_index", { ascending: true });

  // 1. Bronze raw content (the original document)
  if (item.bronze_documents?.raw_content) {
    const raw = item.bronze_documents.raw_content;
    const cleanText = raw.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
    if (cleanText.length > 100) {
      const text = cleanText.slice(0, 12000);
      sourceTexts.push({
        label: `Original document: ${item.source_id}`,
        text,
      });
      totalChars += text.length;
    }
  }

  // 2. Document chunks linked to this item
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

  // 3. Related chunks via raw_metadata keywords (if bronze content was thin)
  if (sourceTexts.length <= 1 && item.bronze_documents?.raw_metadata) {
    const meta = item.bronze_documents.raw_metadata;
    const subjects = (meta.subjects || meta.keywords || []) as string[];
    if (subjects.length > 0) {
      const { data: relatedChunks } = await db
        .from("document_chunks")
        .select("chunk_text, section_path")
        .eq("jurisdiction", item.jurisdiction)
        .neq("source_id", id)
        .limit(5);

      if (relatedChunks) {
        for (const chunk of relatedChunks) {
          if (totalChars >= MAX_CONTEXT_CHARS) break;
          const text = chunk.chunk_text.slice(0, 4000);
          sourceTexts.push({
            label: chunk.section_path || "Related law",
            text,
          });
          totalChars += text.length;
        }
      }
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
