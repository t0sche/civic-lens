import { createServerClient } from "@/lib/supabase-client";
import { statusColor, jurisdictionLabel } from "@/lib/badges";
import config from "../../civic-lens.config.json";

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
  const db = createServerClient();
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

// @spec DASH-VIEW-001, DASH-VIEW-002
export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ jurisdiction?: string }>;
}) {
  const params = await searchParams;
  const jurisdiction = (params.jurisdiction || "ALL") as JurisdictionFilter;
  const items = await fetchLegislativeItems(jurisdiction);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Legislative Tracker</h1>
        <p className="mt-1 text-sm text-gray-600">
          {`Active and proposed legislation affecting ${config.display.subtitle} (${config.zip}) across state, county, and municipal governments.`}
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
              <a
                key={item.id}
                href={`/legislation/${item.id}`}
                className="block rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md hover:border-gray-300"
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
                      {item.title}
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
                  <svg
                    className="mt-1 h-4 w-4 flex-shrink-0 text-gray-300"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </div>
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
