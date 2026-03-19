/**
 * Stats API endpoint — returns locality info, data source freshness,
 * record counts, and pipeline health.
 *
 * GET /api/stats
 */

import { NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase-client";
import { getLocality, getJurisdictionNames } from "@/lib/locality";

export async function GET() {
  const db = createServerClient();
  const loc = getLocality();

  const jurisdictions = getJurisdictionNames();

  // Latest ingestion run per source
  const { data: runs, error: runsError } = await db
    .from("ingestion_runs")
    .select(
      "source,status,started_at,completed_at,records_fetched,records_new,records_updated,error_message"
    )
    .order("started_at", { ascending: false });

  if (runsError) {
    return NextResponse.json(
      {
        error: "Failed to fetch latest ingestion runs",
        details: runsError.message ?? runsError,
      },
      { status: 500 },
    );
  }

  // Deduplicate to latest per source
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const latestBySource: Record<string, any> = {};
  for (const run of runs || []) {
    if (!latestBySource[run.source]) {
      latestBySource[run.source] = run;
    }
  }

  // Record counts
  const [bronze, legislative, codeSections, chunks] = await Promise.all([
    db.from("bronze_documents").select("id", { count: "exact", head: true }),
    db.from("legislative_items").select("id", { count: "exact", head: true }),
    db.from("code_sections").select("id", { count: "exact", head: true }),
    db.from("document_chunks").select("id", { count: "exact", head: true }),
  ]);

  const countError =
    bronze.error || legislative.error || codeSections.error || chunks.error;

  if (countError) {
    return NextResponse.json(
      {
        error: "Failed to fetch record counts",
        details:
          (bronze.error && bronze.error.message) ||
          (legislative.error && legislative.error.message) ||
          (codeSections.error && codeSections.error.message) ||
          (chunks.error && chunks.error.message) ||
          countError,
      },
      { status: 500 },
    );
  }

  // Pipeline health: embedding coverage
  const silverTotal = (legislative.count ?? 0) + (codeSections.count ?? 0);
  const goldTotal = chunks.count ?? 0;
  const embeddingCoverage = silverTotal > 0 ? Math.round((goldTotal / silverTotal) * 100) : 0;

  return NextResponse.json({
    locality: {
      zip: loc.zip,
      name: loc.locality.name,
      jurisdictions,
    },
    dataSources: Object.values(latestBySource).map((run) => ({
      source: run.source,
      status: run.status,
      startedAt: run.started_at,
      completedAt: run.completed_at,
      recordsFetched: run.records_fetched,
      recordsNew: run.records_new,
      recordsUpdated: run.records_updated,
      errorMessage: run.error_message,
    })),
    counts: {
      bronze: bronze.count ?? 0,
      legislativeItems: legislative.count ?? 0,
      codeSections: codeSections.count ?? 0,
      documentChunks: goldTotal,
    },
    pipeline: {
      silverTotal,
      goldTotal,
      embeddingCoveragePercent: embeddingCoverage,
    },
  });
}
