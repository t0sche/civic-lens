import { createClient } from "@supabase/supabase-js";

// Server-side Supabase client for SSR data fetching
function getSupabase() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );
}

type JurisdictionFilter = "ALL" | "STATE" | "COUNTY" | "MUNICIPAL";

interface LegislativeItem {
  id: string;
  source_id: string;
  jurisdiction: string;
  body: string;
  item_type: string;
  title: string;
  summary: string | null;
  status: string;
  introduced_date: string | null;
  last_action_date: string | null;
  last_action: string | null;
  sponsors: string[];
  source_url: string | null;
  tags: string[];
}

// @spec DASH-VIEW-001
async function fetchLegislativeItems(
  jurisdiction?: JurisdictionFilter
): Promise<LegislativeItem[]> {
  const db = getSupabase();
  let query = db
    .from("legislative_items")
    .select("*")
    .order("last_action_date", { ascending: false, nullsFirst: false })
    .limit(50);

  if (jurisdiction && jurisdiction !== "ALL") {
    query = query.eq("jurisdiction", jurisdiction);
  }

  const { data, error } = await query;
  if (error) {
    console.error("Failed to fetch legislative items:", error);
    return [];
  }
  return data || [];
}

// Status badge color mapping
function statusColor(status: string): string {
  const colors: Record<string, string> = {
    INTRODUCED: "bg-blue-100 text-blue-800",
    IN_COMMITTEE: "bg-yellow-100 text-yellow-800",
    PASSED_ONE_CHAMBER: "bg-indigo-100 text-indigo-800",
    ENACTED: "bg-green-100 text-green-800",
    APPROVED: "bg-green-100 text-green-800",
    EFFECTIVE: "bg-green-100 text-green-800",
    VETOED: "bg-red-100 text-red-800",
    REJECTED: "bg-red-100 text-red-800",
    EXPIRED: "bg-gray-100 text-gray-800",
    PENDING: "bg-amber-100 text-amber-800",
    TABLED: "bg-orange-100 text-orange-800",
    UNKNOWN: "bg-gray-100 text-gray-600",
  };
  return colors[status] || colors.UNKNOWN;
}

// Jurisdiction label styling
function jurisdictionLabel(jurisdiction: string): {
  text: string;
  className: string;
} {
  const labels: Record<string, { text: string; className: string }> = {
    STATE: { text: "State", className: "bg-purple-100 text-purple-800" },
    COUNTY: { text: "County", className: "bg-teal-100 text-teal-800" },
    MUNICIPAL: { text: "Municipal", className: "bg-sky-100 text-sky-800" },
  };
  return labels[jurisdiction] || { text: jurisdiction, className: "bg-gray-100 text-gray-800" };
}

// @spec DASH-VIEW-001, DASH-VIEW-002
export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ jurisdiction?: string }>;
}) {
  const { jurisdiction: rawJurisdiction } = await searchParams;
  const jurisdiction = (rawJurisdiction || "ALL") as JurisdictionFilter;
  const items = await fetchLegislativeItems(jurisdiction);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Legislative Tracker</h1>
        <p className="mt-1 text-sm text-gray-600">
          Active and proposed legislation affecting Bel Air, MD (21015) across
          state, county, and municipal governments.
        </p>
      </div>

      {/* Jurisdiction Filter */}
      <div className="mb-6 flex gap-2">
        {(["ALL", "STATE", "COUNTY", "MUNICIPAL"] as const).map((j) => (
          <a
            key={j}
            href={`/?jurisdiction=${j}`}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
              jurisdiction === j
                ? "bg-gray-900 text-white"
                : "bg-gray-100 text-gray-700 hover:bg-gray-200"
            }`}
          >
            {j === "ALL" ? "All" : jurisdictionLabel(j).text}
          </a>
        ))}
      </div>

      {/* Legislative Items */}
      {items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 py-12 text-center">
          <p className="text-gray-500">
            No legislative items found. Data ingestion may not have run yet.
          </p>
          <p className="mt-2 text-sm text-gray-400">
            Check the ingestion pipeline status in GitHub Actions.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const jLabel = jurisdictionLabel(item.jurisdiction);
            return (
              <div
                key={item.id}
                className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${jLabel.className}`}
                      >
                        {jLabel.text}
                      </span>
                      <span
                        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(
                          item.status
                        )}`}
                      >
                        {item.status.replace(/_/g, " ")}
                      </span>
                      <span className="text-xs text-gray-400">
                        {item.source_id}
                      </span>
                    </div>
                    <h3 className="text-sm font-semibold leading-snug">
                      {item.source_url ? (
                        <a
                          href={item.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:text-blue-600 hover:underline"
                        >
                          {item.title}
                        </a>
                      ) : (
                        item.title
                      )}
                    </h3>
                    {item.summary && (
                      <p className="mt-1 text-xs text-gray-600 line-clamp-2">
                        {item.summary}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-gray-500">
                      <span>{item.body}</span>
                      {item.last_action_date && (
                        <span>Last action: {item.last_action_date}</span>
                      )}
                      {item.last_action && (
                        <span className="truncate max-w-xs">
                          {item.last_action}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
