import { createServerClient } from "@/lib/supabase-client";
import { getLocality, getJurisdictionNames } from "@/lib/locality";

interface IngestionRun {
  id: string;
  source: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  records_fetched: number;
  records_new: number;
  records_updated: number;
  error_message: string | null;
}

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    success: "bg-green-100 text-green-800",
    running: "bg-blue-100 text-blue-800",
    failed: "bg-red-100 text-red-800",
  };
  return colors[status] || "bg-gray-100 text-gray-600";
}

export default async function StatsPage() {
  const db = createServerClient();
  const loc = getLocality();
  const jurisdictions = getJurisdictionNames();

  // Latest ingestion run per source
  const { data: allRuns } = await db
    .from("ingestion_runs")
    .select("*")
    .order("started_at", { ascending: false });

  const latestBySource: Record<string, IngestionRun> = {};
  for (const run of (allRuns || []) as IngestionRun[]) {
    if (!latestBySource[run.source]) {
      latestBySource[run.source] = run;
    }
  }
  const dataSources = Object.values(latestBySource);

  // Record counts
  const [bronze, legislative, codeSections, chunks] = await Promise.all([
    db.from("bronze_documents").select("id", { count: "exact", head: true }),
    db.from("legislative_items").select("id", { count: "exact", head: true }),
    db.from("code_sections").select("id", { count: "exact", head: true }),
    db.from("document_chunks").select("id", { count: "exact", head: true }),
  ]);

  const counts = {
    bronze: bronze.count ?? 0,
    legislativeItems: legislative.count ?? 0,
    codeSections: codeSections.count ?? 0,
    documentChunks: chunks.count ?? 0,
  };

  const silverTotal = counts.legislativeItems + counts.codeSections;
  const embeddingCoverage = silverTotal > 0 ? Math.round((counts.documentChunks / silverTotal) * 100) : 0;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-2xl font-bold">System Stats</h1>
      <p className="mt-1 text-sm text-gray-600">
        Data freshness, coverage, and pipeline health.
      </p>

      {/* Locality Card */}
      <div className="mt-6 rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
          Configured Locality
        </h2>
        <p className="mt-2 text-lg font-bold">{loc.locality.name}</p>
        <p className="text-sm text-gray-600">ZIP: {loc.zip}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {jurisdictions.map((j) => (
            <span
              key={j}
              className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700"
            >
              {j}
            </span>
          ))}
        </div>
      </div>

      {/* Data Sources Table */}
      <div className="mt-6">
        <h2 className="text-lg font-semibold">Data Sources</h2>
        {dataSources.length === 0 ? (
          <p className="mt-2 text-sm text-gray-500">
            No ingestion runs recorded yet.
          </p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-gray-200 text-xs text-gray-500 uppercase">
                <tr>
                  <th className="pb-2 pr-4">Source</th>
                  <th className="pb-2 pr-4">Last Run</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2 pr-4">Fetched</th>
                  <th className="pb-2 pr-4">New</th>
                  <th className="pb-2">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {dataSources.map((run) => (
                  <tr key={run.source}>
                    <td className="py-2 pr-4 font-medium">{run.source}</td>
                    <td className="py-2 pr-4 text-gray-600">
                      {run.started_at ? relativeTime(run.started_at) : "—"}
                    </td>
                    <td className="py-2 pr-4">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge(run.status)}`}
                      >
                        {run.status}
                      </span>
                      {run.error_message && (
                        <span className="ml-2 text-xs text-red-500" title={run.error_message}>
                          (error)
                        </span>
                      )}
                    </td>
                    <td className="py-2 pr-4">{run.records_fetched}</td>
                    <td className="py-2 pr-4">{run.records_new}</td>
                    <td className="py-2">{run.records_updated}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Database Counts */}
      <div className="mt-6">
        <h2 className="text-lg font-semibold">Database</h2>
        <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { label: "Bronze (raw)", value: counts.bronze },
            { label: "Legislative Items", value: counts.legislativeItems },
            { label: "Code Sections", value: counts.codeSections },
            { label: "Document Chunks", value: counts.documentChunks },
          ].map((stat) => (
            <div
              key={stat.label}
              className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
            >
              <p className="text-xs text-gray-500">{stat.label}</p>
              <p className="mt-1 text-2xl font-bold">
                {stat.value.toLocaleString()}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Pipeline Health */}
      <div className="mt-6">
        <h2 className="text-lg font-semibold">Pipeline Health</h2>
        <div className="mt-3 rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600">Embedding Coverage</span>
            <span className="font-medium">
              {embeddingCoverage}% ({counts.documentChunks} chunks / {silverTotal} Silver records)
            </span>
          </div>
          <div className="mt-2 h-3 w-full overflow-hidden rounded-full bg-gray-100">
            <div
              className={`h-full rounded-full transition-all ${
                embeddingCoverage >= 80
                  ? "bg-green-500"
                  : embeddingCoverage >= 50
                    ? "bg-yellow-500"
                    : "bg-red-500"
              }`}
              style={{ width: `${Math.min(embeddingCoverage, 100)}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
